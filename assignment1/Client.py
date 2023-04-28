from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket, threading, sys, traceback, os
import time
from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT

	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3

	counter = 0
	checkplay = False
	checkTeardown = False
	countPayload = 0
	timestart = 0
	timeend = 0
	timeexe = 0
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.frameNbr = 0
	# THIS GUI IS JUST FOR REFERENCE ONLY, STUDENTS HAVE TO CREATE THEIR OWN GUI
	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)

		# Create Play button
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)

		# Create Pause button
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)

		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)

		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.checkTeardown = False
			self.sendRtspRequest(self.SETUP)

	def resetMovie(self):
		if self.checkPlay:
			self.pauseMovie()
			for i in os.listdir():
				if i.find(CACHE_FILE_NAME) == 0:
					os.remove(i)
			time.sleep(1)
			self.checkTeardown = True
			self.state = self.INIT
			# self.master.protocol("WM_DELETE_WINDOW", self.handler)
			self.rtspSeq = 0
			self.sessionId = 0
			self.requestSent = -1
			self.teardownAcked = 0
			self.frameNbr = 0
			self.counter = 0
			self.countPayload = 0
			self.checkPlay = False
			self.timestart = 0
			self.timeend = 0
			self.timeexe = 0
			self.connectToServer()
			self.rtpSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
			self.label.pack_forget()
			self.label.image = ''
	def exitClient(self):
		"""Teardown button handler."""
		if self.state == self.READY and self.timeexe:
			print("Video data rate = {0} / {1} = {2} ".format(self.countPayload,self.timeexe,self.countPayload / self.timeexe))

		self.sendRtspRequest(self.TEARDOWN)
		self.master.destroy()  # Close the gui window
		os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT)  # Delete the cache image from video

		if self.frameNbr:
			rate = float((self.frameNbr - self.counter)/ self.frameNbr)
			print("\nPacket loss rate: " + str(rate) + "\n")
		sys.exit(0)

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.timeend = time.time()
			self.timeexe += self.timeend - self.timestart
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			# Create a new thread to listen for RTP packets
			self.timestart = time.time()
			self.checkPlay = True
			threading.Thread(target=self.listenRtp).start()
			self.playEvent = threading.Event()
			self.playEvent.clear()
			self.sendRtspRequest(self.PLAY)

	def listenRtp(self):
		"""Listen for RTP packets."""
		while True:
			try:
				data = self.rtpSocket.recv(20480)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)

					currFrameNbr = rtpPacket.seqNum()
					self.counter += 1
					print("Current Seq Num: " + str(currFrameNbr))

					if currFrameNbr > self.frameNbr:  # Discard the late packet
						self.frameNbr = currFrameNbr
						self.countPayload += len(rtpPacket.getPayload())
						self.updateMovie(self.writeFrame(rtpPacket.getPayload()))

			except:
				# Stop listening upon requesting PAUSE or TEARDOWN
				if self.state == self.PLAYING:
					self.pauseMovie()
					print("\nLast packet is received")
				print("not receive data!")
				if self.playEvent.isSet():
					break

				# Upon receiving ACK for TEARDOWN request,
				# close the RTP socket
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break

	def writeFrame(self, data):
		"""Write the received frame to a temp image file. Return the image file."""
		cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
		file = open(cachename, "wb")
		file.write(data)
		file.close()

		return cachename

	def updateMovie(self, imageFile):
		"""Update the image file as video frame in the GUI."""
		# photo = ImageTk.PhotoImage(Image.open(imageFile))
		# self.label.configure(image=photo, height=288)
		# self.label.image = photo
		try:
			photo = ImageTk.PhotoImage(Image.open(imageFile)) #stuck here !!!!!!
		except:
			print("photo error")

		if self.checkTeardown:
			self.label.configure(image = '', height=288)
			self.label.image = ''
		else:
			self.label.configure(image = photo, height=288)
			self.label.image = photo
	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	#TODO
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		#-------------
		# TO COMPLETE
		#-------------
		if requestCode is self.SETUP and self.state is self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			self.rtspSeq = 1
			request = "SETUP " + str(self.fileName) + " RTSP/1.0"+"\n" + "CSeq: " + str(self.rtspSeq) + "\nTRANSPORT: RTP/UDP; " + "client_prot= " + str(self.rtpPort)
			self.rtspSocket.send(request.encode())
			self.requestSent = self.SETUP
		elif requestCode is self.PLAY and self.state is self.READY:
			self.rtspSeq = self.rtspSeq + 1
			request = "PLAY " + str(self.fileName) + " RTSP/1.0"+"\n" + "CSeq: " + str(self.rtspSeq) + "\n" + "Session: " + str(self.sessionId)
			self.rtspSocket.send(request.encode())
			self.requestSent = self.PLAY
		elif requestCode is self.PAUSE and self.state is self.PLAYING:
			self.rtspSeq = self.rtspSeq + 1
			request = "PAUSE " + str(self.fileName) + " RTSP/1.0"+"\n" + "CSeq: " + str(self.rtspSeq) + "\n" + "Session: " + str(self.sessionId)
			self.rtspSocket.send(request.encode())
			self.requestSent = self.PAUSE
		elif requestCode is self.TEARDOWN and self.state is not self.INIT:
			self.rtspSeq = self.rtspSeq + 1
			request = "TEARDOWN " + str(self.fileName) + " RTSP/1.0"+"\n" + "CSeq: " + str(self.rtspSeq) + "\n" + "Session: " + str(self.sessionId)
			self.rtspSocket.send(request.encode())
			self.requestSent = self.TEARDOWN
		else:
			return
		print("\nData sent: \n" + request)
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		#TODO

		while True:
			data = self.rtspSocket.recv(1024)
			if data:
				self.parseRtspReply(data.decode("utf-8"))
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		#
		# S: RTSP/1.0 200 OK
		# S: CSeq: 1
		# S: Session: 123456
		#
		lines = data.split('\n')
		seqnum = int(lines[1].split(' ')[1])
		session = int(lines[2].split(' ')[1])
		if self.sessionId == 0:
			self.sessionId = session
		#update state
		if self.requestSent == self.SETUP:
			self.state = self.READY
			self.openRtpPort()
		elif self.requestSent == self.PLAY:
			self.state = self.PLAYING
		elif self.requestSent == self.PAUSE:
			self.state = self.READY
			self.playEvent.set()
		else:
			self.state = self.INIT
			self.teardownAcked = 1

	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# -------------
		# TO COMPLETE
		# -------------
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.rtpSocket.settimeout(0.5)
		# Set the timeout value of the socket to 0.5sec
		# ...
		try:
			self.rtpSocket.bind((self.serverAddr, self.rtpPort))
			# self.rtpSocket.listen(5)
			print ("Bind RtpPort Success")
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)


	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()
