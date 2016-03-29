RIFT.ware 
=========
### RIFT.ware version 4.1.1.0 release notes
Updated March 29, 2016


### RIFT.ware version 4.1.0.1 release notes
Updated February 29, 2016

RIFT.ware version 4.1.0.1  is the first public release of RIFT.ware 4.1. It is available as RPMs and as source.  See https://open.riftio.com for the latest updates, files, and documentation.

## Build and install instructions 
Please refer https://open.riftio.com/webdocs/RIFTware/Authoring/Installation/InstallRiftwareFromSource.htm

## Known Issues

* MANO:
RIFT-11934, RIFT-11916 -- Launchpad will be slow and may fail with a heartbeat error if the VM in which it runs is under-resourced. 

* Opensource: 
The Build VM is missing some packages. 
After instantiating the BUILD VM (qcow image downloadable at https://open.riftio.com/download/),  before running your first build, you must install some packages.
This is a one time change

<pre>
yum install libdb-devel
sed -i "s/eng.riftio.com/riftio.com/g" /usr/rift/bin/pip3-install
/usr/rift/bin/pip3-install jujuclient
</pre>

### For questions or issues
Visit https://support.riftio.com
