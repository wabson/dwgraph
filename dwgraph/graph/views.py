from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.http import HttpResponse, Http404
import json

# Create your views here.

def home(request):
    return render_to_response('graph/index.html', {}, context_instance=RequestContext(request))

def graph(request):
    return render_to_response('graph/graph.html', {}, context_instance=RequestContext(request))

def data(request):
    _l = []
    for i in []:
         j = {}
         _l.append(j)
    return HttpResponse(json.dumps(_l), mimetype='application/json')
