import requests
import json
import memcache
import socket
import json
import datetime
import re
import sys
from subprocess import check_output
from os import path

history_file_path = path.join(path.dirname(path.abspath(__file__)), 'history.json')

settings = {}
history = {}

def update_number_widget(dashboard_name, widget, value):
	widget = dashboard_name + '_' + widget
	old_value = history.get(widget)
	payload = {
		'auth_token': settings.get('dashing-auth-token'),
		'current': value
	}

	if old_value is not None:		
		payload.update({'last': old_value})

	requests.post(settings.get('dashing-url') + 'widgets/' + widget, data=json.dumps(payload))	
	history.update({ widget: value})

def update_graph_widget(dashboard_name, widget, value):
	widget = dashboard_name + '_' + widget
	points = history.get(widget)
	payload = {
		'auth_token': settings.get('dashing-auth-token')		
	}

	if points is None:		
		points = []

	last_x = 1
	for point in points:
		last_x = max(last_x, point['x'])

	points.append({ 'x': last_x + 1, 'y': value})
	points = points[-10:]
	payload.update({'points': points})

	requests.post(settings.get('dashing-url') + 'widgets/' + widget, data=json.dumps(payload))
	history.update({ widget: points})

def update_text_widget(dashboard_name, widget, text):
	widget = dashboard_name + '_' + widget
	payload = {
		'auth_token': settings.get('dashing-auth-token'),
		'text': text
	}

	requests.post(settings.get('dashing-url') + 'widgets/' + widget, data=json.dumps(payload))

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
	try:
		settings_file = open(path.join(path.dirname(path.abspath(__file__)), 'settings.json'))
		settings = json.load(settings_file)
		settings_file.close()

		# Try to load local settings if they exist
		try:
			settings_file = open(path.join(path.dirname(path.abspath(__file__)), 'local_settings.json'))
			settings.update(json.load(settings_file))
			settings_file.close()
		except IOError:
			pass

		if settings.get('dashing-url') == '':
			raise Exception(u'Please specify dashing-url in settings file')

		if settings.get('dashing-auth-token') == '':
			raise Exception(u'Please specify dashing-auth-token in settings file')

		dashboard_name = settings.get('worker-name')

		# Initialize history object
		try:
			history_file = open(history_file_path)
			history = json.load(history_file)
			history_file.close()
		except IOError:
			pass

		summary = get_minerd_summary(settings.get('minerd-address'), settings.get('minerd-port'))
		update_graph_widget(dashboard_name, 'khs', float(summary['SUMMARY'][0]['MHS 5s']) * 1000)
		update_number_widget(dashboard_name, 'accepted', summary['SUMMARY'][0]['Accepted'])
		update_number_widget(dashboard_name, 'rejected', summary['SUMMARY'][0]['Rejected'])
		update_number_widget(dashboard_name, 'errors', summary['SUMMARY'][0]['Hardware Errors'])	
		elapsed = str(datetime.timedelta(seconds=int(summary['SUMMARY'][0]['Elapsed'])))
		update_text_widget(dashboard_name, 'elapsed', elapsed)
		# update_graph_widget(dashboard_name, 'temperature', get_gpu_temperature(current_dashboard['GPU_SENSOR_NUMBER']))

		# Save history object
		with open(history_file_path, 'w+') as history_file:
			json.dump(history, history_file)

	except IOError:
		raise Exception(u'Missing settings.json file')