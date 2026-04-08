from django.urls import path, re_path
import graph.views

urlpatterns = [
    path('', graph.views.home, name='home'),
    path('graph', graph.views.graph, name='graph'),
    re_path(r'^\d{4}$', graph.views.graph_archive, name='graph_archive'),
    path('data', graph.views.data, name='data'),
    path('crewdata', graph.views.crew_data, name='crew_data'),
]
