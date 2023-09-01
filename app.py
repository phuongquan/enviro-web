import datetime as dt
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import pandas as pd
import math
import plotly.express as px
import requests as req
import json
import io
from flask_restful import Api, Resource
from flask import request
# store credentials in a file called cred.py in root folder
import cred
import config

log_activity = False

def log_message(msg):
    if log_activity:
        with open('log.txt', 'a') as f:
            f.write(str(dt.datetime.now()) + ': ' + msg + '\n')

def load_enviro_readings():
    log_message('load_enviro_readings start')

    data = get_gist_readings()['data']
    data["timestamp"] = pd.to_datetime(data['timestamp'], utc=True)
    log_message('load_enviro_readings end')
    return data

def get_gist_readings(last_only=False):
    # get latest version of data from gist
    gist_response = req.get(url='https://api.github.com/gists/' + config.gist_uid,
    headers= dict([('Accept', 'application/vnd.github+json'),
        ('Authorization', 'Bearer ' + cred.github_pat),
        ('X-GitHub-Api-Version', '2022-11-28')])) 
    
    gist_files = list(gist_response.json()['files'].keys())
    # TODO: filter to only files that match regexp
    if last_only:
        gist_files.sort(reverse=True)
        relevant_files = [gist_files[0]]
    else:
        gist_files.sort()
        relevant_files = gist_files

    data = pd.DataFrame()
    for gf in relevant_files:
        content = gist_response.json()['files'][gf]['content']
        data = pd.concat([data, pd.read_csv(io.StringIO(content))])
    
    return {'data': data, 'lastfilename': gf}
    
def save_enviro_readings(newdata):
    log_message('save_enviro_readings start')

    lastsaveddata = get_gist_readings(last_only=True)
    # gist api truncates data when over 1mb so keep files under that size
    if len(lastsaveddata['data']) + len(newdata) > 1500:
        insert_pos = config.gist_filename.find('.csv')
        savefilename = config.gist_filename[:insert_pos] \
        + "_" + str(dt.datetime.now()).replace(" ", "T").replace(":", "").replace("-", "")[0:15] \
        + config.gist_filename[insert_pos:]
        data = newdata
    else:
        savefilename = lastsaveddata['lastfilename']
        data = pd.concat([lastsaveddata['data'], newdata])
 
    payload = {'files': {savefilename:{'content':data.to_csv(index=False)}}}

    req.patch(url = 'https://api.github.com/gists/' + config.gist_uid,
    headers = dict([('Accept', 'application/vnd.github+json'),
        ('Authorization', 'Bearer ' + cred.github_pat),
        ('X-GitHub-Api-Version', '2022-11-28')]),
        data = json.dumps(payload))
    log_message('save_enviro_readings end')
    return True

def round_up_ten(x):
    if x == None or math.isnan(x) or x==0:
        retval = 10
    else:
        retval = int(math.ceil((x + 1) / 10)) * 10
    return retval

def plot_readings(type, data):
    log_message('plot_readings start' + ': ' + type)
    if len(data) == 0:
        xrange = [dt.date.today(), dt.date.today() + dt.timedelta(days=1)]
    else:
        xrange = [min(data["timestamp"]) - dt.timedelta(days=1), max(data["timestamp"]) + dt.timedelta(days=1)]

    if type=="temperature":
        p = px.scatter(
            data,
            x='timestamp', y='temperature',
            range_x=xrange,
            range_y=[-10,50],
            color_discrete_sequence=['darkorange'])
    elif type=="humidity":
        p = px.scatter(
            data,
            x='timestamp', y='humidity',
            range_x=xrange,
            range_y=[0,100], 
            color_discrete_sequence=['mediumblue'])
    elif type=="pressure":
        p = px.scatter(
            data,
            x='timestamp', y='pressure',
            range_x=xrange,
            range_y=[900, 1100],
            color_discrete_sequence=['olive'])
    elif type=="noise":
        p = px.scatter(
            data,
            x='timestamp', y='noise',
            range_x=xrange,
            range_y=[0, round_up_ten(data.max()['noise'])],
            color_discrete_sequence=['purple'])
    elif type=="pm1":
        p = px.scatter(
            data,
            x='timestamp', y='pm1',
            range_x=xrange,
            range_y=[0, round_up_ten(data.max()['pm1'])],
            color_discrete_sequence=['darkgrey'])
    elif type=="pm25":
        p = px.scatter(
            data,
            x='timestamp', y='pm2_5',
            range_x=xrange,
            range_y=[0, round_up_ten(data.max()['pm2_5'])], 
            color_discrete_sequence=['grey'])
    elif type=="pm10":
        p = px.scatter(
            data,
            x='timestamp', y='pm10',
            range_x=xrange,
            range_y=[0, round_up_ten(data.max()['pm10'])], 
            color_discrete_sequence=['dimgrey'])
        
    p.update_layout(showlegend=False)
    log_message('plot_readings end')
    return p


app = dash.Dash(__name__)
server = app.server

app.title = config.site_title
app.config.suppress_callback_exceptions = False

api = Api(app.server)

class receive_data(Resource):
    def post(self):
        if not (request.authorization['username'] == config.enviro_custom_http_username and request.authorization['password'] == config.enviro_custom_http_password):
            return "Authentication failed", 401

        reqjson = json.loads(request.data.decode('utf-8'))
        # make sure single readings are in a list
        if type(reqjson) == dict:
            newreadings = []
            newreadings.append(reqjson)
        else:
            newreadings = reqjson
        # only attempt to save relevant readings
        counter = 0
        data = pd.DataFrame()
        for line in newreadings:
            if line['nickname'] == config.enviro_nickname:
                new_row = pd.DataFrame({
                    'timestamp': [line['timestamp']],
                    'temperature': [line['readings']['temperature']],
                    'humidity': [line['readings']['humidity']],
                    'pressure': [line['readings']['pressure']],
                    'noise': [line['readings']['noise']],
                    'pm1': [line['readings']['pm1']],
                    'pm2_5': [line['readings']['pm2_5']],
                    'pm10': [line['readings']['pm10']]
                    })
                data = pd.concat([data, new_row])
                counter += 1
            else:
                # ignore row
                msg = 'invalid source'
                
        if save_enviro_readings(data):
            return f"{counter} readings saved for: {config.enviro_nickname}", 200

        return "Unknown failure", 400

api.add_resource(receive_data, '/envirodata')

def serve_layout():
    enviro_readings = load_enviro_readings()
    return html.Div(
    [
        dcc.Location(id='url'),
        html.Div(
            [
                html.H2(config.site_title,
                style={'padding': 10}),
            ],
            className='app__header'
        ),
        html.Div(
            [
                html.Button(
                    'TEST ENVIRO POST',
                    id='save-enviro',
                    className='submit__button',
                ),
                html.Span(id='test-output')
            ],
            hidden=False
        ),
        html.Div(
            [
                dcc.Tabs(
                    id='tabs',
                    value='view-graphs',
                    children=[
                        dcc.Tab(
                            label='GRAPHS',
                            value='view-graphs',
                            children=[
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-temperature',
                                        figure=plot_readings("temperature", enviro_readings),
                                        className='graph__1'),
                                        
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-humidity',
                                        figure=plot_readings("humidity", enviro_readings),
                                        className='graph__1'),
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-pressure',
                                        figure=plot_readings("pressure", enviro_readings),
                                        className='graph__1')
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-noise',
                                        figure=plot_readings("noise", enviro_readings),
                                        className='graph__1')
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-pm1',
                                        figure=plot_readings("pm1", enviro_readings),
                                        className='graph__1')
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-pm25',
                                        figure=plot_readings("pm25", enviro_readings),
                                        className='graph__1')
                                    ],
                                    className='graph__container',
                                ),
                                html.Div(
                                    [
                                        dcc.Graph(id='plot-pm10',
                                        figure=plot_readings("pm10", enviro_readings),
                                        className='graph__1')
                                    ],
                                    className='graph__container',
                                ),
                           ],
                        ),
                        dcc.Tab(
                            label='ABOUT',
                            value='about',
                            children=[
                                html.Div(
                                    [
                                        dcc.Markdown('''

                                        Details about this implementation

                                        ''')
                                    ],
                                    className='container__1'
                                )
                            ],
                        )
                    ],
                )
            ],
            className='tabs__container',
        ),
        html.Div(
            [
                dcc.Markdown('''
                ''')
            ],
            className='app__footer',
        ),
    ],
    className='app__container',
)

app.layout = serve_layout


@app.callback(
    Output('test-output', 'children'),
    Input('save-enviro', 'n_clicks'),
    prevent_initial_call=True
)
def test_enviro(save_enviro_clicks):
    auth = (config.enviro_custom_http_username, config.enviro_custom_http_password)
    target = 'http://127.0.0.1:8050/envirodata'
#    target = 'https://mysite.pythonanywhere.com/envirodata'

#    reading = json.load(open(f"2023-01-08T17_32_33Z.json", "r"))
#    result = req.post(url=target, auth=auth, json=reading)

    newreadings = []
    with open(f"2023-01-24.txt", "rt") as f:
        # get column headings
        headings = f.readline().rstrip('\n').split(',')
        # and assume first is timestamp
        headings.pop(0)
        for line in f:
            data = line.rstrip('\n').split(',')
            readings = {
                "nickname": config.enviro_nickname,
                "timestamp": data.pop(0),
                "readings": dict(zip(headings, data)),
                "model": "urban",
                "uid": "notused"
            }
            newreadings.append(readings)
    result = req.post(url=target, auth=auth, json=newreadings)

    result.close()  
    return f"{result.status_code} {result.text}"


if __name__ == '__main__':
    app.run_server(debug=True)