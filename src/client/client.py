import sys
import selectors
import socket
import os
from flask import Flask, render_template, redirect, url_for
app = Flask(__name__)

sys.path.insert(0, "../")

from messages.dns_request_message import *
from messages.dns_response_message import *
from messages.client_req_lb_message import *
from messages.client_res_lb_message import *
from messages.content_related_messages import *
from config import *
from edgeServer.edgeServer import md5

############# Get IP of load balancer from DNS

s = socket.socket()         
host = DNS_IP ## DNS_IP
port = DNS_PORT            

s.connect((host, port))

print("Requesting IP from DNS")
msg = DNSRequestMessage(1, "www.mycdn.com")
msg.send(s)

msg = DNSResponseMessage()
msg.receive(s)
ipblocks = msg.ipblocks
print(ipblocks)

s.close()

############# Request file from load balancer
def connectLB(ipblocks):

	"""
	Method to connect to LBs
	IP blocks contains the DNS response
	"""

	err_count = 0

	for host, port in ipblocks:
		s = socket.socket()
		try:
			print("Connecting ",host,":",port)
			s.connect((host, port))
			print("Connected ",host,":",port)
			break
		except socket.error:
			err_count += 1
			print("Connection failed ",host,":",port)
			continue

	if err_count == 2:
		print("Load Balancer could not be reached!")
		return s,0
	else:
		print("Connection established to the load balancer")
		return s,1

############# Request file from redirected IP of edge server

def requestFile(edgeIP,edgePort,content_id,seq_no=0):
	
	## Sequence number is zero for initial request
	## returns last sequence number it received 
	## -2 if complete file is received
	## -1 if nothing is received
	## else the sequence number

	soc = socket.socket()
	soc.settimeout(30)
	
	try:
		print("Connecting to edge server ip: ",edgeIP)
		sys.stdout.flush()
		soc.connect((edgeIP, edgePort))
	except Exception as e:
		print("Unable to connect to edge server ip: ",edgeIP)
		return -1
	
	last_seq_number_recv = -1
	message = ContentRequestMessage(content_id, seq_no)
	message.send(soc)

	file_des = FileDescriptionMessage(0, 0, '', '')
	
	try:
		file_des.receive(soc)
	except:
		print("Unable to get file details")
		print("Last Sequence Number received: ",last_seq_number_recv)
		return last_seq_number_recv
	
	print(file_des.file_name)
	print(file_des.content_id)
	print(file_des.file_size)
	if seq_no!=0:
		param = 'ab'
	else:
		param = 'wb'
	with open('static/css/' + file_des.file_name, param) as f:
		print('file opened')
		print("Content ID: ",file_des.content_id)
		if seq_no!=0:
			f.seek(seq_no*1018)
		file_size = file_des.file_size
		total_received=seq_no*1018
		while True:
			msg = ContentMessage(content_id, seq_no)

			try:
				msg.receive(soc,file_size,total_received)
			except Exception as e:
				print("Last Sequence Number received: ",last_seq_number_recv)
				print(e)
				return last_seq_number_recv
			
			# print("Sequence no: ",msg.seq_no)
			last_seq_number_recv = msg.seq_no
			data = msg.data
			total_received+=len(data)
			# print(len(data))
			if not data:
				break
			f.write(data)
	f.close()
	soc.close()

############# Verify file, close connections and show success
	
	if md5('/static/css/'+file_des.file_name)==file_des.md5_val:
		print("File download success!")
	else:
		print("MD5 does not match")
		os.remove('/static/css/'+file_des.file_name)
		print("Try downloading again")		
	return -2

def get_file(cont, i):
	contentReq = int(cont)	
		
	seqNo = -1
	location_id = i
	n_msg = ClientReqLBMessage(contentReq,location_id)
	prev_edge_ip = n_msg.prev_edge_ip

		# seqNo = requestFile(msg.ip, EDGE_SERVER_PORT ,contentReq)
	if seqNo != -2:		
		s, err = connectLB(ipblocks)
		if err==0:
			input("Load Balancer could not be reached!")
		n_msg = ClientReqLBMessage(contentReq,location_id,prev_edge_ip)
		try:
			# input("Press enter to request new edge server")
			n_msg.send(s)
			# print('Hi')
			n_msg = ClientResLBMessage()
			n_msg.receive(s)
			prev_edge_ip = n_msg.ip
			# input("Press enter to connect to edge server!")
			if n_msg.ip=='0.0.0.0':
				print("No edge servers available.")
				input("Press enter to try again!")

			seqNo = requestFile(n_msg.ip, EDGE_SERVER_PORT ,contentReq, seqNo+1)
		except:
			pass
		s.close()
	else:
		pass


#############

@app.route('/')
def index():
	return render_template('index.html')

@app.route('/get_css')
def getCss():
	get_file("1234",1)
	return redirect(url_for('index'))

@app.route('/get_image')
def getImage():
	get_file("5678",2)
	return redirect(url_for('index'))

if __name__ == "__main__":
	app.run(host='0.0.0.0', port=80)