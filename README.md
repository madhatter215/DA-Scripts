# DA-Scripts

addUvmRegBackdoor.py requires https://pypi.python.org/pypi/regex

Note: I was unable to install due to using an older version of GCC on the SLE linux system we are using. The steps below will save a lot of time to complete the install. 
Reason: Build flag 'wno-unused-result' not supported in gcc version that comes with SLE we are using


	• python3 -m pip freeze
	• python3 -m pip show <module>
		○ to see where other user modules are installed
	• setenv CFLAGS "-pthread -Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Wstrict-prototypes -fPIC"
	• python3 setup.py build
	• setenv PYTHONHOME /pkg/software/python/3.5.2
	• python3 setup.py install --prefix=/usr2/$USER/.local
  	○ point to directory from second step above
