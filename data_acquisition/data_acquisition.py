# Don't listen to foen
# new version
# second change
# camera branch
# first commit to camera

import sys
import serial as s
import threading
from os import listdir, mkdir, remove
from shutil import move
from datetime import date
from time import sleep
from threading import Thread

class flowerController(Thread):

	def __init__(self, port, accel_sample_freq):
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
				self.raw_data = open(self.rawfilename, 'wb')
				# Send samples rates and start command
				cmd = bytearray("{0}\n".format(self.accel_sample_freq), 'ascii')
				self.ser.write(cmd)
				success = True
			except BaseException:
				success = False
				raise(e)
		if success:
			self.running = True
		else:
			self.running = False

	"""
	This function implements the running Loop of the
	FlowerController thread. It waits for 3-byte frames
	of data from the arduino and writes them to a separate
	file based on the first byte, the code, of the data.
	"""
	def run(self):
		self.begin()
		self.ser.flushInput()
		nectar_present = False
		while self.running:
			# Read 3-bytes from the serial port
			while(self.ser.in_waiting):
				# Read two frames worth of data and write to raw file
				data = self.ser.read(24)
				self.raw_data.write(data)

				# Parse the data for a nectar measurement
				nectar_value = None
				for i in range(len(data)):
					# Check for the data code
					if data[i] == ord('N') and i+1 in range(len(data)):
						if i-3 in range(len(data)):
							# Check to make sure that the previous value was from Z channel
							if data[i-3] == ord('Z'):
								nectar_value = data[i+1]
								break
						if i+3 in range(len(data)):
							# Check to make sure that the following value is form X channel
							if data[i+3] == ord('X'):
								nectar_value = data[i+1]
								break
				# Determine the nectar state
				if nectar_value is not None:
					if nectar_present and nectar_value >= 150:
						nectar_present = False
					elif not nectar_present and nectar_value <= 75:
						nectar_present = True

		self.stop()

	def stop(self):
		# Assert Data Terminal Ready to reset Arduino
		self.ser.dtr = True
		sleep(1)
		self.ser.dtr = False
		# Close the port
		self.ser.close()
		# Unpack the data
		self.unpack_data()
		# Fix the time overflow issue
		try:

			update_time(self.Xfilename, 4 * self.accel_sample_freq)
			update_time(self.Yfilename, 4 * self.accel_sample_freq)
			update_time(self.Zfilename, 4 * self.accel_sample_freq)
			update_time(self.Nfilename, 4 * self.accel_sample_freq)

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
	This function reads from the raw binary data file and separates each
	data frame, where a frame consists of one read from each analog input channel
	and its corresponding timestamp.

	After collecting the frames, it will compute the amount of bytes lost in
	transmission, and then write the data to appropriate files (one for each channel)
	"""
	def unpack_data(self):
		# Close the raw_data file, since it was open for writing previously
		self.raw_data.close()
		# Open the raw data file for reading
		self.raw_data = open(self.rawfilename, 'rb')
		data = bytearray()

		# Iterate over the file, reading each byte and appending to an array
		while True:
			byte = self.raw_data.read(1)
			if byte:
				data += byte
			else:
				break

		index = 0						# iteration index
		frames = []						# Location of frames in the data array
		while(index + 11 < len(data)):	# Verify that there is a full frame yet to be processed
			if locate_frame(index,data):
				frames.append(index)	# Append this index to a list of indexes pointing to valid frames
				index += 12				# Increment by the size of one frame in bytes
			else:
				index += 1				# Increment by one byte

		print("frame count", len(frames))
		print("bytes received", len(data))
		bytes_lost = len(data) - len(frames) * 12
		print("bytes lost", bytes_lost)
		print("loss ratio " + str(100 * bytes_lost / len(data)) + " percent" )

		for frame in frames:
			# Write the X value and timestamp to the CSV file
			value = data[frame+1]
			timestamp = data[frame+2]
			line = "{0},{1}\n".format(value,timestamp)
			self.Xfile.write(line)

			# Write the Y value and timestamp to the CSV file
			value = data[frame+4]
			timestamp = data[frame+5]
			line = "{0},{1}\n".format(value,timestamp)
			self.Yfile.write(line)

			# Write the Z value and timestamp to the CSV file
			value = data[frame+7]
			timestamp = data[frame+8]
			line = "{0},{1}\n".format(value,timestamp)
			self.Zfile.write(line)

			# Write the N value and timestamp to the CSV file
			value = data[frame + 10]
			timestamp = data[frame + 11]
			line = "{0},{1}\n".format(value,timestamp)
			self.Nfile.write(line)

		# Close the output files
		self.Xfile.close()
		self.Yfile.close()
		self.Zfile.close()
		self.Nfile.close()
		self.Efile.close()
		self.Ifile.close()

def locate_frame(index,data):
	if data[index] != ord("X"):
		return False
	elif data[index + 3] != ord("Y"):
		return False
	elif data[index + 6] != ord("Z"):
		return False
	elif data[index + 9] != ord("N"):
		return False
	else:
		return True


"""
This function is used to adjust the time stamps sent by
the flower controller after the data has been unpacked and sorted
into separate files.

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
	if(3 != len(sys.argv)):
		userError ="""
		dataAcquisition.py requires two input arguments:

		1) serial port device file
		2) accellerometer sample rate (Hz) - must be a positive integer!

		Example of use: python3 dataAcquisition.py /dev/ttyACM0 1000"""
		raise Exception(userError)
		exit()
	accel_sample_freq = int(sys.argv[2])
	actual_accel_freq = int(16000000/(16000000/accel_sample_freq - 1))
	print("Sample rate, {0}".format(actual_accel_freq))
	f = flowerController(sys.argv[1], accel_sample_freq)
	input("enter anything to begin\n")
	print("output is being written to " + f.folder)
	f.start()
	input("enter anything to terminate\n")
	f.running = False
	print("active threads " + str(threading.active_count()))
	f.join()
	print("Goodbye!")
