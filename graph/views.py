from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.http import HttpResponse, Http404
import json
import re
from datetime import datetime, timedelta, date

# Create your views here.

this_year = 2016
last_year = this_year - 1
archives = range(2007, this_year - 1)

def home(request):
    return render_to_response('graph/index.html', {'current_year': this_year, 'year': this_year, 'last_year': last_year, 'archives': archives}, context_instance=RequestContext(request))

def graph(request):
    return render_to_response('graph/graph.html', {'current_year': this_year, 'year': this_year, 'last_year': last_year, 'archives': archives}, context_instance=RequestContext(request))

def graph_archive(request):
    current_year = int(request.path[1:]) # Strip off initial '/'
    return render_to_response('graph/graph.html', {'current_year': current_year, 'year': this_year, 'last_year': last_year, 'archives': archives}, context_instance=RequestContext(request))

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

# Dates of Easter Sunday
easter_dates = {
    2002: (3, 31),
    2003: (4, 20),
    2004: (4, 11),
    2005: (3, 27),
    2006: (4, 16),
    2007: (4, 8),
    2008: (3, 23),
    2009: (4, 12),
    2010: (4, 4),
    2011: (4, 24),
    2012: (4, 8),
    2013: (3, 31),
    2014: (4, 20),
    2015: (4, 5),
    2016: (3, 27),
    2017: (4, 16),
    2018: (4, 1),
    2019: (4, 21),
    2020: (4, 12)
}

def km_to_mi(d):
    return d * 0.621371192

def get_easter_date(year):
    #row = scraperwiki.sqlite.select("* from easter_dates.swdata where year = %s" % (year))[0]
    #return date(row['year'], row['month'], row['day'])
    y = int(year)
    (m, d) = easter_dates[y]
    return date(y, m, d)

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

def __get_arrival_time(year, location, row):
    timestr = row.get('time_%s' % (location)) or row.get('time_%s_arr' % (location))
    return daytime_to_datetime(year, timestr.replace('rtd ', '')) if timestr is not None else None

def __get_departure_time(year, location, row):
    timestr = row.get('time_%s' % (location)) or row.get('time_%s_dep' % (location))
    return daytime_to_datetime(year, timestr.replace('rtd ', '')) if timestr is not None else None

def __is_retired(location, row):
    timestr = row.get('time_%s' % (location)) or row.get('time_%s_arr' % (location))
    return timestr.startswith('rtd') if timestr is not None else False

def calculate_crew_data(year, row):
    lastdist = 0.0
    lasttime = None
    cdata = {}
    missing_locs = [] # any stages for which timing data is missing
    for loc in locations:
        stage_data = None
        retired = __is_retired(loc, row)
        atime = __get_arrival_time(year, loc, row)
        dtime = __get_departure_time(year, loc, row)
        if (atime is not None):
            sdist = distances[loc]
            stage_dist = sdist - lastdist
            stage_time = atime - lasttime if lasttime is not None else None
            stage_speed = stage_dist / (stage_time.seconds / 3600.0) if (stage_time is not None and stage_time.seconds > 0) else None
            if stage_speed > 20:
                stage_speed = None
            stage_data = {
                'split_dist': sdist,
                'split_time': atime,
                'stage_dist': stage_dist,
                'stage_time': stage_time,
                'stage_speed': stage_speed,
                'retired': retired
            }
            cdata[loc] = stage_data

            lastdist = sdist
            lasttime = dtime
        else:
            missing_locs.append(loc)

        if stage_data is not None and len(missing_locs) > 0:
            for loc in missing_locs:
                cdata[loc] = stage_data
            missing_locs = []
    return cdata

def get_result_locations(datalocations):
    abbr_locations = [ l.replace('time_', '') for l in locations ]
    return dict(zip(abbr_locations, [({'speed': km_to_mi(datalocations[loc]['stage_speed']) if datalocations[loc]['stage_speed'] is not None else None, 'retired': datalocations[loc]['retired']} if loc in datalocations else {'name': loc, 'retired': True, 'stage_speed': None}) for loc in locations]))
        

def build_crew_data(row):
    crews = []
    crews.append({'firstname': row['firstname_1'], 'surname': row['surname_1'], 'club': row['club_1']})
    if row['surname_2'] is not None and row['surname_2'] != '':
        crews.append({'firstname': row['firstname_2'], 'surname': row['surname_2'], 'club': row['club_2']})
    return crews

def __dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def __get_overnight_locations_query(year, boat_nums):
    return __get_locations_query(year, 'locations', boat_nums)

def __get_fourday_locations_query(year, boat_nums):
    return __get_locations_query(year, 'locations_4d', boat_nums)

def __get_locations_query(year, loc_table, boat_nums):
    query_params = { 'year': int(year), 'loc_table': loc_table, 'boats': ', '.join([str(int(bn)) for bn in boat_nums])}
    return "select %(loc_table)s.*, firstname_1, firstname_2, surname_1, surname_2, club_1, club_2, class_position as position, class_results.elapsed_time from %(loc_table)s JOIN class_results on %(loc_table)s.boat_number=class_results.boat_number and %(loc_table)s.year=class_results.year where class_results.year = '%(year)s' and class_results.boat_number IN (%(boats)s)" % query_params

def __get_crew_query(year, text):
    query_params = { 'year': int(year), 'text': text}
    return "select boat_number, firstname_1, firstname_2, surname_1, surname_2, club_1, club_2 from class_results where class_results.year = '%(year)s' and (surname_1 LIKE '%%%(text)s%%' OR surname_2 LIKE '%%%(text)s%%')" % query_params

def __get_crew_by_num(year, boat_num):
    query_params = { 'year': int(year), 'boat_num': int(boat_num)}
    return "select boat_number, firstname_1, firstname_2, surname_1, surname_2, club_1, club_2 from class_results where class_results.year = '%(year)s' and boat_number = '%(boat_num)s'" % query_params

def __get_query_data(query):
    from django.db import connections
    cursor = connections['data'].cursor()
    try:
        cursor.execute(query);
        return __dictfetchall(cursor)
    except ValueError, e:
        return None

def data(request):
    year = int(request.GET.get('y', '0'))
    boat_nums = [int(x) for x in request.GET.get('bn', '0').split(',') if re.match('\d+$', x) is not None]
    cb = request.GET.get('callback', 'callback')
    rows = __get_query_data(__get_overnight_locations_query(year, boat_nums))
    rows.extend(__get_query_data(__get_fourday_locations_query(year, boat_nums)))
    data = [{'boat_number': row['boat_number'], 'crew': build_crew_data(row), 'position': row['position'], 'time': row['elapsed_time'], 'locations': calculate_crew_data(year, row), 'retired': row['status'].startswith('rtd'), 'disqualified': row['status'].startswith('dsq')} for row in rows]
    _d = {'results': [{'boat_number': d['boat_number'], 'position': d['position'] , 'time': d['time'], 'crew': d['crew'], 'locations': get_result_locations(d['locations'])} for d in data], 'year': year}
    return HttpResponse('%s(%s)' % (cb, json.dumps(_d)), content_type='application/json')


def crew_data(request):
    year = int(request.GET.get('y', '0'))
    query = request.GET.get('q', '')
    cb = request.GET.get('callback', 'callback')
    data = []
    if len(query) >= 3:
        if re.match('\d+$', query):
            rows = __get_query_data(__get_crew_by_num(year, int(query)))
        else:
            filtered_query = re.sub('[^\w -]', '', query)
            rows = __get_query_data(__get_crew_query(year, filtered_query))
        data = [{'boat_number': row['boat_number'], 'crew': build_crew_data(row)} for row in rows]
    _d = {'results': data, 'year': year}
    return HttpResponse('%s(%s)' % (cb, json.dumps(_d)), content_type='application/json')
