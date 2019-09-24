import json
import random
import msvcrt
import os
import keyboard
from datetime import datetime
import time
from cryptography.fernet import Fernet

# helper function to see if 'q' is in keyboard buffer
def qInBuffer():
	while msvcrt.kbhit(): # exists letters in keyboard buffer
		if msvcrt.getch().decode() == 'q': # pop a letter
			return True
	return False

class FSManager:

	def __init__( self, metadataAddr ):
		self.metadataAddr = metadataAddr
		self.data = self.importMetadata()

	
	# safe way to import metadata
	def importMetadata( self ):
		# check metadata file exists
		exists = os.path.exists( self.metadataAddr )
		if not exists:
			cfrm = input( "Unable to locate metadata file '{}'. Create one? (Y/n)\n".format( self.metadataAddr ) )
			if str.lower( cfrm ) != "y":
				print( "Operation aborted." )
				return
			try:
				data_file = open( self.metadataAddr, "w" )
				data_file.close()
			except IOError:
				print ( "Unable to create metadata file." )
				return None
		
		# check metadata file has content to protect from JSON errors
		if os.stat( self.metadataAddr ).st_size == 0:
			if exists:
				print( "Initializing metadata file." )
			try:
				data_file = open( self.metadataAddr, "w" )
			except IOError:
				print ( "Unable to initialize metadata file." )
				return None
			with data_file:
				data_file.write( json.dumps( { "systems": {} }, indent=3 ) )

		# decode the JSON
		try:
			data_file = open( self.metadataAddr, "r+" )
		except IOError:
			print ( "Unable to read metadata." )
			return None
		with data_file:
			try:
				data = json.load( data_file )
			except Exception:
				print( "Error decoding metadata file." )
				return None
			return data
	
	
	# create new file system and save it
	def createFileSystem( self, fsName ):

		# import metadata
		newData = self.importMetadata()
		if newData is None:
			print( "Unable to import metadata." )
			return
		
		# check if already exists
		if fsName in self.data[ 'systems' ]:
			cfrm = input( "File system '{}' already exists, overwrite cached data? (Y/n)\n".format( fsName ) )
			if str.lower( cfrm ) != "y":
				print( "Operation aborted." )
				return

		# create new filesystem in memory
		self.data[ 'systems' ][ fsName ] = {
			'files': {},
			'key': Fernet.generate_key().decode() # UTF-8
			}

		print( "File system '{}' created.".format( fsName ) )

		# save systems
		self.saveSystems()

	# show all data about a specific file system
	def showFileSystem( self, fsName ):
		# sync local -> file -> local
		self.saveSystems()
		self.data = self.importMetadata()
		if self.data is None:
			print( "Unable to commit, couldn't import metadata." )
			return

		# check file system exists
		if fsName not in self.data[ 'systems' ]:
			cfrm = input( "System '{}' doesn't exist. Create it? (Y/n)\n".format( fsName ) )
			if str.lower( cfrm ) == "y":
				self.createFileSystem( fsName )
				return
		
		# print data
		fsData = self.data[ 'systems' ][ fsName ]
		print( "*** {} ***".format( fsName ) )
		print( " - key: {}".format( fsData[ 'key' ] ) )
		print( " - files:" )
		for fileName, fileData in fsData[ 'files' ].items():
			if fileData:
				fMessage = "encrypted as '{}' at {} UTC".format( fileData[ 'uuid' ],
															 datetime.fromtimestamp( fileData[ 'time' ] ) )
			else:
				fMessage = "not yet encrypted"
			print( "   - {} {}".format( fileName, fMessage) )



	# update metadata file to match given list of file systems= 
	def saveSystems( self ):

		# grab data metadata file
		existingData = self.importMetadata()
		if existingData is None:
			print( "Can't save, unable to import existing metadata." )
			return

		# make appropriate changes to existing systems
		for fs in existingData[ 'systems' ]:
			if fs in self.data[ 'systems' ]:
				existingData[ 'systems' ][ fs ] = self.data[ 'systems' ][ fs ] # overwrite with local changes
		
		# tack on any new systems
		for fs, data in self.data[ 'systems' ].items():
			existingData[ 'systems' ][ fs ] = data

		# overwrite metadata file
		with open( self.metadataAddr, "w" ) as data_file:
			data_file.write( json.dumps( existingData, indent=3 ) )

		print( "Systems saved." )


	# add a file address to a given system
	def addFileToSystem( self, fsName, addr ):

		# sync local -> file -> local
		self.saveSystems()
		self.data = self.importMetadata()
		if self.data is None:
			print( "Unable to commit, couldn't import metadata." )
			return

		if fsName not in self.data[ 'systems' ]:
			cfrm = input( "System '{}' doesn't exist. Create it? (Y/n)\n".format( fsName ) )
			if str.lower( cfrm ) == "y":
				self.createFileSystem( fsName )
		else:
			if addr not in self.data[ 'systems' ][ fsName ][ 'files' ]:
				self.data[ 'systems' ][ fsName ][ 'files' ][ addr ] = {} # data assigned during encrypting
			# save metadata
			self.saveSystems()

	
	# encrypt an entire file system or a single file from a file system
	def encryptFileSystem( self, fsName, fileName=None ):

		# sync local -> file -> local
		self.saveSystems()
		self.data = self.importMetadata()
		if self.data is None:
			print( "Unable to commit, couldn't import metadata." )
			return

		# encrypt each file
		if fsName not in self.data[ 'systems' ]:
			cfrm = input( "System '{}' doesn't exist. Create it? (Y/n)\n".format( fsName ) )
			if str.lower( cfrm ) == "y":
				self.createFileSystem( fsName )
				return

		filesToEncrypt = [ fileName ] if fileName is not None else self.data[ 'systems' ][ fsName ][ 'files' ]
		if filesToEncrypt:
			for fAddr in filesToEncrypt:
				# check file exists
				if not os.path.exists( fAddr ):
					print( "File '{}' not found.".format( fAddr ) )
					return
				# assign a globally unique ID to the file (32 chars)
				if 'uuid' in self.data[ 'systems' ][ fsName ][ 'files' ][ fAddr ]:
					uuid = self.data[ 'systems' ][ fsName ][ 'files' ][ fAddr ][ 'uuid' ]
				else:
					uuids = []
					for __, data in self.data[ 'systems' ].items():
						for __, id in data[ 'files' ].items():
							uuids.append( id )
					while True:
						uuid = "{}".format( hex( random.getrandbits( 128 ) ) )[ 2 : ]
						if uuid not in uuids:
							break
					self.data[ 'systems' ][ fsName ][ 'files' ][ fAddr ][ 'uuid' ] = uuid

				# encrypt file using filesystem's key
				with open( fAddr, "rb") as f:
					bData = f.read()
				
				fHandler = Fernet( self.data[ 'systems' ][ fsName ][ 'key' ] )
				encryptedBData = fHandler.encrypt(bData)

				# write encrypted binary to shadow file in crypt
				with open( "crypt/{}".format( uuid ), "wb+") as cryptFile:
					cryptFile.write(encryptedBData)

				# take timestamp and record encryption time in seconds
				self.data[ 'systems' ][ fsName ][ 'files' ][ fAddr ][ 'time' ] = round( time.time() )
		else:
			print( "No files to encrypt! Add some using the 'add' command." )
		# write systems
		self.saveSystems()
 

	# update a file system by checking its watch-list
	def updateFileSystem( self, fsName ):

		# sync local -> file -> local
		self.saveSystems()
		self.data = self.importMetadata()
		if self.data is None:
			print( "Unable to update file systems, couldn't import metadata." )
			return
		
		if fsName not in self.data[ 'systems' ]:
			print( "System not found." )

		# if any file is newer than its encryption date, re-encrypt it
		for fAddr, info in self.data[ 'systems' ][ fsName ][ 'files' ].items():
			lastModified = os.path.getmtime( fAddr )
			encrypted = info[ 'time' ]
			if lastModified > encrypted:
				print( "Change detected in '{}', re-encrypting file.".format( fAddr ) )
				self.encryptFileSystem( fsName, fAddr )

	# continually watch and update a filesystem
	def watchFileSystem( self, fsName ):
		while True:
			if qInBuffer():
				print( "No longer watching '{}'.".format( fsName ) )
				break
			self.updateFileSystem( fsName )
			time.sleep( 1 )
			
	
