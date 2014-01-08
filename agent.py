import requests
import json
import memcache
import socket
import json
import datetime
import re
import sys
from subprocess import check_output

try:
	import settings
except ImportError:
	raise Exception(u'Missing settings.py file')

mc = memcache.Client(settings.MEMCACHED)

def update_number_widget(dashboard_name, widget, value):
	widget = dashboard_name + '_' + widget
	old_value = mc.get(settings.MEMCACHED_PREFIX + widget)
	payload = {
		'auth_token': settings.DASHING_AUTH_TOKEN,
		'current': value
	}

	if old_value is not None:		
		payload.update({'last': old_value})

	requests.post(settings.DASHING_URL + 'widgets/' + widget, data=json.dumps(payload))
	mc.set(settings.MEMCACHED_PREFIX + widget, value, 0)

def update_graph_widget(dashboard_name, widget, value):
	widget = dashboard_name + '_' + widget
	points = mc.get(settings.MEMCACHED_PREFIX + widget)
	payload = {
		'auth_token': settings.DASHING_AUTH_TOKEN		
	}

	if points is None:		
		points = []

	last_x = 1
	for point in points:
		last_x = max(last_x, point['x'])

	points.append({ 'x': last_x + 1, 'y': value})
	points = points[-10:]
	payload.update({'points': points})

	requests.post(settings.DASHING_URL + 'widgets/' + widget, data=json.dumps(payload))
	mc.set(settings.MEMCACHED_PREFIX + widget, points, 0)

def update_text_widget(dashboard_name, widget, text):
	widget = dashboard_name + '_' + widget
	payload = {
		'auth_token': settings.DASHING_AUTH_TOKEN,
		'text': text
	}

	requests.post(settings.DASHING_URL + 'widgets/' + widget, data=json.dumps(payload))

def get_minerd_summary(address, port):
	minerd_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	minerd_socket.connect((address, port))
	minerd_socket.sendall('{"command":"summary"}')
	received_data = minerd_socket.recv(4096)
	summary = json.loads(received_data[:-1])

	return summary

def get_gpu_temperature(sensor):
	if sys.platform == 'linux2':
		output = check_output(['/usr/bin/aticonfig', '--odgt'])
		matches = re.search("Sensor %s: Temperature - ([0-9]+\.[0-9]+)" % (str(sensor),), output)

		if matches is not None:			
			return float(matches.group(1))

	return -1

if __name__ == '__main__':
	for dashboard_name in settings.DASHBOARDS:
		current_dashboard = settings.DASHBOARDS[dashboard_name]
		summary = get_minerd_summary(current_dashboard['MINERD_ADDRESS'], current_dashboard['MINERD_PORT'])
		update_graph_widget(dashboard_name, 'khs', float(summary['SUMMARY'][0]['MHS 5s']) * 1000)
		update_number_widget(dashboard_name, 'accepted', summary['SUMMARY'][0]['Accepted'])
		update_number_widget(dashboard_name, 'rejected', summary['SUMMARY'][0]['Rejected'])
		update_number_widget(dashboard_name, 'errors', summary['SUMMARY'][0]['Hardware Errors'])	
		elapsed = str(datetime.timedelta(seconds=int(summary['SUMMARY'][0]['Elapsed'])))
		update_text_widget(dashboard_name, 'elapsed', elapsed)
		update_graph_widget(dashboard_name, 'temperature', get_gpu_temperature(current_dashboard['GPU_SENSOR_NUMBER']))	

