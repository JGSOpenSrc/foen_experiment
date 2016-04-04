import sys
import serial as s
import threading
from os import listdir, mkdir, remove
from shutil import move
from datetime import date
from time import sleep
from threading import Thread

class flowerController(Thread):

	def __init__(self, port, accel_sample_freq,
				 nectar_sample_freq):
		Thread.__init__(self)
		# Declare filenames to write in output folder
		self.Xfilename = "x_data.csv"
		self.Yfilename = "y_data.csv"
		self.Zfilename = "z_data.csv"
		self.Nfilename = "n_data.csv"
		self.Efilename = "e_data.csv"
		self.Ifilename = "i_data.csv"
		self.rawfilename = "raw_data"
		# Get the morphology to name the output folder
		morph = input("Which morphology is it?\n")
		today = date.today()
		# Get the date, also used to name output folder
		self.folder = morph + "_" + str(today)
		# Determine number of trials of morphology present in this folder
		directory = listdir()
		trials = 0
		for item in directory:
			index = item.rfind(self.folder + "_trial_")
			if(index == 0):
				trials += 1
	    # create folder <date>_<morphology>_<X>/
		self.folder = self.folder +"_trial_" + str(trials+1)
		try:
			mkdir(self.folder)
		except:
			print("failed to make working directory\n")
		# Open output files in working directory
		self.Xfilename = self.folder + "/" + self.Xfilename
		self.Yfilename = self.folder + "/" + self.Yfilename
		self.Zfilename = self.folder + "/" + self.Zfilename
		self.Nfilename = self.folder + "/" + self.Nfilename
		self.Efilename = self.folder + "/" + self.Efilename
		self.Ifilename = self.folder + "/" + self.Ifilename
		self.rawfilename = self.folder + "/" + self.rawfilename

		self.port = port
		self.running = False

		self.accel_sample_freq = accel_sample_freq
		self.nectar_sample_freq = nectar_sample_freq

	def begin(self):
		try:
			# Open port at 1Mbit/sec
			self.ser = s.Serial(self.port,
									1000000,
									timeout = 1)
			success = True
			# Assert Data Terminal Ready signal to reset Arduino
			self.ser.rtscts = True
			self.ser.dtr = True
			sleep(1)
			self.ser.dtr = False
			sleep(3)
		except s.SerialException:
			success = False
			print("Failed to open " + self.port + "\n")
			raise(s.SerialException)

		if success:
			try:
				# Open output files for wriging
				self.Xfile = open(self.Xfilename, 'w')
				self.Yfile = open(self.Yfilename, 'w')
				self.Zfile = open(self.Zfilename, 'w')
				self.Nfile = open(self.Nfilename, 'w')
				self.Efile = open(self.Efilename, 'w')
				self.Ifile = open(self.Ifilename, 'w')
				# Send samples rates and start command
				self.ser.flushInput()
				cmd = bytearray("{0}\n".format(self.accel_sample_freq), 'ascii')
				self.ser.write(cmd)
				sleep(1)
				cmd = bytearray("{0}\n".format(self.nectar_sample_freq), 'ascii')
				self.ser.write(cmd)
				success = True
			except BaseException:
				success = False
				raise(e)
		if success:
			self.running = True
		else:
			self.running = False

	def stop(self):
		# Assert Data Terminal Ready to reset Arduino
		self.ser.dtr = True
		sleep(1)
		self.ser.dtr = False
		# Close the port
		self.ser.close()
		# Close the output files
		self.Xfile.close()
		self.Yfile.close()
		self.Zfile.close()
		self.Nfile.close()
		self.Efile.close()
		self.Ifile.close()
		# Fix the time overflow issue
		try:
			update_time(self.Xfilename, 4 * self.accel_sample_freq)
			update_time(self.Yfilename, 4 * self.accel_sample_freq)
			update_time(self.Zfilename, 4 * self.accel_sample_freq)
			update_time(self.Nfilename, self.nectar_sample_freq)
			update_time(self.Efilename, 1)
			update_time(self.Ifilename, 1)
			pass
		except OSError as e:
			raise(e)
		# Write the comments file
		try:
			commentfile = self.folder + "/comments.txt"
			comments = input("Comments on this trial?\n")
			filename = open(commentfile, 'w')
			filename.write(comments)
			filename.close()
		except OSError as e:
			raise(e)
	"""
	This function implements the running Loop of the
	FlowerController thread. It waits for 3-byte frames
	of data from the arduino and writes them to a separate
	file based on the first byte, the code, of the data.
	"""
	def run(self):
		self.begin()
		while self.running:
			data = ""
			# Read 3-bytes from the serial port
			data = self.ser.readline()
			# Sometimes a value looks like EOL, in that case,
			# read a nother value
			if(2 == len(data)):
				data = [data, self.ser.read(2)]
			try:
				# Test to make sure there is actual data to process
				if(len(data)>0):
					# if <code>: write data to file corresponding to <code>
					if(ord('X') == data[0]):
						val = str(data[1])
						time = str(data[2])
						line = "{0},{1}\n".format(val,time)
						self.Xfile.write(line)
					elif (ord('Y') == data[0]):
						val = str(data[1])
						time = str(data[2])
						line = "{0},{1}\n".format(val,time)
						self.Yfile.write(line)
					elif (ord('Z') == data[0]):
						val = str(data[1])
						time = str(data[2])
						line = "{0},{1}\n".format(val,time)
						self.Zfile.write(line)
					elif (ord('N') == data[0]):
						val = str(data[1])
						time = str(data[2])
						line = "{0},{1}\n".format(val,time)
						self.Nfile.write(line)
					elif (ord('E') == data[0]):
						val = str(data[1])
						time = str(data[2])
						line = "{0},{1}\n".format(val,time)
						self.Efile.write(line)
						if(1 == data[1]):
							print("Nectar filled at time stamp {0}".format(time))
						elif(0 == data[1]):
							print("Nectar emptied at time stamp {0}".format(time))
					elif (ord('I') == data[0]):
						time = str(data[2])
						line = ",{0}\n".format(time);
						print("Injection requested at time stamp {0}".format(time))
						self.Ifile.write(line)
			except ValueError:
				print("ValueError: junk data caught in flowerController.run()")
		self.stop()
"""
This function is used to adjust the time stamps sent by
the flower controller.

For example, the sequence of time stamps
0, 1, ..., 2^16-1, 0, 1, ... 2^16-1 is converted into
0, 1, ..., 2^16-1, 2^16, 2^16+1, ..., 2^17-1
"""
def update_time(filename, frequency):
	print("Updating " + filename)
	# open the file for reading
	try:
		in_file = open(filename, 'r')
	except OSError:
		raise OSError("Error opening " + filename + "for reading!")
	# Loop over the file contents, and then process
	lines = list()
	offset = 0;
	last_time = 0;
	modulus = pow(2,8)
	for line in in_file:
		# split the data into (data,time_stamp)
		(data, sep, time_stamp) = line.partition(',')
		time_stamp = int(time_stamp.rstrip('\n'))
		# Adjust the time_stamp
		time_stamp += offset * modulus
		# If the time has decreased suddenly, then the value has overflowed
		if(time_stamp < last_time):
			offset += 1
			time_stamp += modulus
		# Record last time to check for overflow on next iteration
		last_time = time_stamp
		# Convert the time_stamp to seconds with 6 digits of precision
		(integer, dot, fraction) = str(time_stamp / frequency).partition('.')
		if(6 < len(fraction)):
			fraction = fraction[0:6]
		time_stamp = "".join((integer, dot, fraction))
		# Rejoin the parts to a new line, and write to file
		if('' == data):
			lines.append(time_stamp+'\n')
		else:
			lines.append("".join((data,sep,time_stamp))+'\n')
	in_file.close()
	# Open the file for writing
	try:
		out_file = open(filename,'w')
	# OSError caught incase the file does not exist or this
	# script does not have permissions to write
	except OSError:
		print("Error opening " + filename + " for writing!")
		raise OSError
	# Write the data to the file
	for line in lines:
		out_file.write(line)
	# All done with this file
	out_file.close()

if __name__ == "__main__":
	if(4 != len(sys.argv)):
		userError ="""
		dataAcquisition.py requires three input arguments:

		1) serial port device file
		2) accellerometer sample rate (Hz) - must be a positive integer!
		3) nectar sample rate (Hz) - must be a positive integer!

		Example of use: python3 dataAcquisition.py /dev/ttyACM0 1000 100"""
		raise Exception(userError)
		exit()
	accel_sample_freq = int(sys.argv[2])
	nectar_sample_freq = int(sys.argv[3])
	actual_accel_freq = int(16000000/(16000000/accel_sample_freq - 1))
	actual_nectar_freq = int(actual_accel_freq * nectar_sample_freq / accel_sample_freq)
	print("Sample rates, {0}, {1}".format(actual_accel_freq, actual_nectar_freq))
	f = flowerController(sys.argv[1],
	 					 accel_sample_freq,
						 nectar_sample_freq)
	input("enter anything to begin\n")
	print("output is being written to " + f.folder)
	f.start()
	input("enter anything to terminate\n")
	f.running = False
	print("active threads " + str(threading.active_count()))
	f.join()
	print("Goodbye!")
