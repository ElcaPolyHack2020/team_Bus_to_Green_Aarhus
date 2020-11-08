import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go
#import plotly.express as px
import pandas as pd
from dash.dependencies import Input, Output
import numpy as np
#import dash_bootstrap_components as dbc
#import glob

from collections import Counter

#external_stylesheets=[dbc.themes.CYBORG,'assets/style.css']
app = dash.Dash(__name__)#, external_stylesheets=external_stylesheets)
server = app.server

#df = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/earthquakes-23k.csv')

busdf=pd.read_json('data/buses.json')#pd.DataFrame({'hour':[np.random.randint(0,high=24) for i in range(0,100)],'bus_id':[np.random.randint(0,high=20) for i in range(0,100)],'occupancy':np.random.rand(100),'total_km':np.random.rand(100)*100.})#pd.read_csv('data/buses.csv')

pass_df=pd.DataFrame({'hour':[np.random.randint(0,high=24) for i in range(0,5000)],'passenger_id':[np.random.randint(0,high=500) for i in range(0,5000)],'status':[np.random.randint(0,high=3) for i in range(0,5000)]})#pd.read_csv('data/buses.csv')


app.layout = html.Div(children=[
    html.H1(children='Buses for a Better Aarhus',style={'margin-top': '50px','margin-bottom': '25px', 'display': 'inline-block','font-size': '3em'}),
        html.Div(className='row',children=[
                html.Div(className='one column div-user-controls'),
                html.Div(className='ten columns div-for-charts bg-grey',children=[html.Div(id='map'),dcc.Slider(id='hour',min=0,max=24,step=1,marks={i:str(i) for i in range(0,25)},value=0),
                html.H3("Time of Day") ],style={'height': '100%', 'display': 'inline-block'})
               ]),
        html.Div(className='row',children=[
            html.Div(className='one column div-user-controls'),
            html.Div(className='ten columns div-for-charts bg-grey',children=[dcc.Graph(id='scatter')],style={'height': '100%', 'display': 'inline-block'})
            ]),
#        html.Div(className='row',children=[
#        html.Div(className='one column div-user-controls'),
#        html.Div(className='ten columns div-for-charts bg-grey',children=[dcc.Graph(id='dfig')],style={'height': '100%', 'display': 'inline-block'})
#        ]),
        html.Div(className='row',children=[
        html.Div(className='one column div-user-controls'),
        html.Div(className='ten columns div-for-charts bg-grey',children=[
        #dbc.Row([dbc.Col(dcc.Graph(id='buses'),width=4), dbc.Col(dcc.Graph(id='passengers'),width=4)])
        html.Div(dcc.Graph(id='buses')),
        html.Div(dcc.Graph(id='dfig')),
        html.Div(dcc.Graph(id='passengers'))],style={'height':'100%','display': 'inline-block'})
        #]),
        ]),
#        html.Div(className='row',children=[
#                html.Div(className='one column div-user-controls'),
#                html.Div(className='ten columns div-for-charts bg-grey',children=[dcc.Graph(id='buses')])],style={'width': '100%', 'display': 'inline-block'}),
#        html.Div(className='row',children=[html.Div(className='one column div-user-controls'),html.Div(className='ten columns div-for-charts bg-grey',children=[dcc.Graph(id='passengers')])],style={'width': '100%', 'display': 'inline-block'}),

    html.Div(className='row',children=[html.Div(children=[
        html.P(""),
        html.P("Polyhack 2020, Team Bus to Green Aarhus"),
        html.P("V. Contucci, E. Lastufka, Y. Müller, P. Schärli"),
        html.P("contact: elastufka@gmail.com")],style={'margin-left':'20px'})])
])


############ Transmission ###############
@app.callback(
    [Output('map', 'children'),Output('scatter', 'figure'),Output('buses', 'figure'),Output('dfig', 'figure'),Output('passengers', 'figure')],
    Input('hour', 'value'))
    #Input('attenuator', 'value'),
    #Input('athick', 'value'),
    #Input('detector', 'value'),
    #Input('dthick', 'value')


def update_graph(hour):#,attenuator,athick,detector,dthick):

    #mfig = go.Figure() #fake map for now

    limits = [(0,2),(3,10),(11,20),(21,50),(50,3000)]
    colors = ["royalblue","crimson","lightseagreen","orange","lightgrey"]

#    mfig.add_trace(go.Choropleth(
#     locations=loc_df['Code'], # Spatial coordinates
#     text = loc_df['Location'],
#     z = loc_df['Count'].astype(float), # Data to be color-coded
#     locationmode = 'USA-states', # set of locations match entries in `locations`
#     colorscale = 'Blues'
#        ))

    #bar chart - buses by ID and occupancy
    bydf=busdf.where(busdf.hour == hour).dropna()
    
    total_km=[]
    occ=[]
    pw,pr,pde=[],[],[]
    for h in range(0,25):
        total_km.append(busdf.where(busdf.hour == h).dropna().total_km.sum())
        occ.append(busdf.where(busdf.hour == h).dropna().occupancy.mean())
        pydf=pass_df.where(pass_df.hour == h).dropna()
        pw.append(pydf.where(pydf.status == 0.0).dropna().status.count())
        pr.append(pydf.where(pydf.status == 1.0).dropna().status.count())
        pde.append(pydf.where(pydf.status == 2.0).dropna().status.count())

    pydf=pass_df.where(pass_df.hour == hour).dropna()
    pwait=pydf.where(pydf.status == 0.0).dropna().status.count()
    priding=pydf.where(pydf.status == 1.0).dropna().status.count()
    pdelivered=pydf.where(pydf.status == 2.0).dropna().status.count()
    #print(pwait,priding,pdelivered)
    #print(total_km)

    #mfig=go.Figure()

    #mfig = px.density_mapbox(df, lat='Latitude', lon='Longitude', z='Magnitude', radius=10,
    #                        center=dict(lat=0, lon=180), zoom=2,
    #                        mapbox_style="stamen-terrain")
        
    try:
        filename='network_'+str(hour)+'.png' #minus teh assets part
        children=html.Div([html.Img(src=app.get_asset_url(filename),width='100%')], style={'textAlign': 'center'})
    except OSError:
        children=html.Div()

    #mfig.add_trace(go.Bar(x=bydf.bus_id,y=bydf.occupancy))
    #mfig.update_layout(title='Bus Occupancy')

    #cumulative scatter over the day -- # ppl in buses vs waiting, number of buses on the road, km travelled

    #km travelled ...

    sfig=go.Figure()
    sfig.add_trace(go.Scatter(x=list(range(0,25)),y=np.array(occ), name='average occupancy (%)'))
    sfig.add_trace(go.Scatter(x=list(range(0,25)),y=total_km, name='distance traveled (km)'))
    sfig.add_trace(go.Scatter(x=list(range(0,25)),y=pw, name='passengers waiting'))
    sfig.add_trace(go.Scatter(x=list(range(0,25)),y=pr, name='passengers riding'))
    sfig.add_trace(go.Scatter(x=list(range(0,25)),y=pde, name='passengers delivered'))
    sfig.update_layout(title='Network Statistics',xaxis_range=[0,3],xaxis_title='Time of Day')

    bydf=busdf.where(busdf.hour == hour).dropna()
    
    bfig=go.Figure()
    bfig.add_trace(go.Bar(x=bydf.bus_id,y=bydf.occupancy))
    bfig.update_layout(title='Bus Occupancy',xaxis_range=[0,50],yaxis_range=[0,100],xaxis_title='Bus Number',yaxis_title='Percent Capacity')
    
    ofig=go.Figure()
    ofig.add_trace(go.Bar(x=bydf.bus_id,y=bydf.total_km))
    ofig.update_layout(title='Distance Traveled',xaxis_range=[0,50],yaxis_range=[0,50],xaxis_title='Bus Number',yaxis_title='Distance (km)')
    
    #pie chart - passengers waiting, riding, delivered

    
    pfig=go.Figure()

    pfig.add_trace(go.Pie(labels=['Waiting','Riding','Delivered'],values=[pwait,priding,pdelivered]))
    pfig.update_layout(title='Passenger Status')
    

    #fig.update_traces(marker=dict(colors=ccolors))
    return children,sfig, bfig, ofig, pfig


#######################################



#######################################


if __name__ == '__main__':
    app.run_server(debug=True)
