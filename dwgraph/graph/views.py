from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.http import HttpResponse, Http404
import json
from datetime import datetime, timedelta, date

# Create your views here.

def home(request):
    return render_to_response('graph/index.html', {}, context_instance=RequestContext(request))

def graph(request):
    return render_to_response('graph/graph.html', {}, context_instance=RequestContext(request))

locations = ['devizes', 'pewsey', 'hford', 'newbury', 'aldermaston', 'reading', 'marsh', 'marlow', 'bray', 'windsor', 'shepperton', 'teddington', 'westminster']

# Distances of each checkpoint in km
distances = {
    'devizes': 0.0,
    'pewsey': 19.227889994,
    'hford': 41.4827534204,
    'newbury': 55.5393448573,
    'aldermaston': 69.5968471956,
    'reading': 87.4062952057,
    'marsh': 98.6132040826,
    'marlow': 113.422632976,
    'bray': 127.201653799,
    'windsor': 140.881688903,
    'shepperton': 156.575465378,
    'teddington': 173.967656418,
    'westminster': 201.332868591
}

def km_to_mi(d):
    return d * 0.621371192

def get_easter_date(year):
    #row = scraperwiki.sqlite.select("* from easter_dates.swdata where year = %s" % (year))[0]
    row = {'year': 2013, 'month': 03, 'day': 31}
    return date(row['year'], row['month'], row['day'])

def daytime_to_datetime(year, daytime):
    days = ['Fri', 'Sat', 'Sun', 'Mon']
    start_date = get_easter_date(year) - timedelta(days=-2) # We need the date of Good Friday, not Sunday
    parts = daytime.split(' ')
    if len(parts) == 2:
        day = parts[0]
        timeparts = parts[1].split(':')
        if len(timeparts) == 3:
            return (datetime(start_date.year, start_date.month, start_date.day, int(timeparts[0]), int(timeparts[1]), int(timeparts[2]))) + (timedelta(days=days.index(day)))
    return None

def calculate_crew_data(year, row):
    lastdist = 0.0
    lasttime = None
    cdata = {}
    missing_locs = [] # any stages for which timing data is missing
    for loc in locations:
        stage_data = None
        retired = str(row['time_%s' % (loc)]).startswith('rtd')
        stime = daytime_to_datetime(year, row['time_%s' % (loc)].replace('rtd ', ''))
        # TODO check if time is marked as retired
        if (stime is not None):
            sdist = distances[loc]
            stage_dist = sdist - lastdist
            stage_time = stime - lasttime if lasttime is not None else None
            stage_speed = stage_dist / (stage_time.seconds / 3600.0) if stage_time is not None else None
            stage_data = {
                'split_dist': sdist,
                'split_time': stime,
                'stage_dist': stage_dist,
                'stage_time': stage_time,
                'stage_speed': stage_speed,
                'retired': retired
            }
            cdata[loc] = stage_data

            lastdist = sdist
            lasttime = stime
        else:
            missing_locs.append(loc)

        if stage_data is not None and len(missing_locs) > 0:
            for loc in missing_locs:
                cdata[loc] = stage_data
            missing_locs = []
    return cdata

def get_result_locations(datalocations):
    return [({'name': loc, 'speed': km_to_mi(datalocations[loc]['stage_speed']) if datalocations[loc]['stage_speed'] is not None else 0.0, 'retired': datalocations[loc]['retired']} if loc in datalocations else {'name': loc, 'retired': True, 'stage_speed': None}) for loc in locations]
        

def build_crew_data(row):
    crews = []
    crews.append({'firstname': row['firstname_1'], 'surname': row['surname_1'], 'club': row['club_1']})
    if row['surname_2'] is not None and row['surname_2'] != '':
        crews.append({'firstname': row['firstname_2'], 'surname': row['surname_2'], 'club': row['club_2']})
    return crews

def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def data(request):
    from django.db import connections
    year = 2013
    boat_nums = request.GET.get('bn', '0').split(',')
    cb = request.GET.get('callback', 'callback')
    cursor = connections['data'].cursor()
    query = "select locations.*, firstname_1, firstname_2, surname_1, surname_2, club_1, club_2, class_position as position, elapsed_time from locations JOIN class_results on locations.boat_number=class_results.boat_number and locations.year=class_results.year where class_results.year = '%s' and class_results.boat_number IN (%s)" % (int(year), '%s' % (int(boat_nums[0])) + ' '.join([(", %s" % int(bn)) for bn in boat_nums[1:]]))
    cursor.execute(query);
    _d = {}
    if (True):
        rows = dictfetchall(cursor)
        data = [{'boat_number': row['boat_number'], 'crew': build_crew_data(row), 'position': row['position'], 'time': row['elapsed_time'], 'locations': calculate_crew_data(year, row), 'retired': row['status'].startswith('rtd'), 'disqualified': row['status'].startswith('dsq')} for row in rows]
        if boat_nums[0] != "all":
            _d = {'results': [{'boat_number': d['boat_number'], 'position': d['position'] , 'time': d['time'], 'crew': d['crew'], 'locations': get_result_locations(d['locations'])} for d in data], 'year': year}
    return HttpResponse('%s(%s)' % (cb, json.dumps(_d)), mimetype='application/json')
