RIFT.ware 
=========


### RIFT.ware version 4.1.1 release notes
Updated March 29, 2016

RIFT.ware version 4.1.1 is available as RPMs and as source code.  See https://open.riftio.com for the latest updates, files, and documentation. 

Build and install instructions are available at https://open.riftio.com/webdocs/RIFTware/Authoring/Installation/InstallRiftwareFromSource.htm

Visit https://support.riftio.com to post questions or raise issues. 


## Known Issues

* RIFT-11508  Onboarding a malformed ping_vnfd package (with incorrect checksum.txt value) succeeds when it should fail with error. 
* RIFT-11508  Onboarding a malformed ping_vnfd package (with incorrect checksum.txt value) succeeds when it should fail with error. 
* RIFT-11507  Onboarding a malformed ping_vnfd package (with incorrect checksum.txt content) succeeds when it should fail with error. 
* RIFT-11489  The RIFT.ware Launchpad fails to detect that a virtual link between ping_vnfd and pong_vnfd has been deleted.
* RIFT-11488  After starting the network service and terminating the ping VM from the OpenStack dashboard, the system fails to report that the ping VM has been terminated.
* RIFT-11416  The RIFT.ware Launchpad Composer page is missing links for About, Debug, and Log.
* RIFT-11305  Adding an unknown attribute to the ping-pong VNF descriptors and network descriptor (ping_vnfd.xml, ping_pong_nsd.xml) causes an onboard failure.
* RIFT-11300  After element <vnfd:internal-connection-point-ref> is removed from an, otherwise, valid descriptor (ping_vnfd.xml), the onboarding step incorrectly succeeds. This element is an internal reference for the VNFD. The omission is discovered during network service instantiation only. 
* RIFT-11095  An image exported from the RIFT.ware UI does not include the type of NFV object in its name, such as VNFD or NSD.
* RIFT-10949  After starting a new RW.CLI session, you can safely ignore the message, "Error: failed to add cli mode: node”, as long as the rift-shell prompt ("rift#") is also received.
* In 4.1.1, if the operator tries to use the Logs feature, LogAnalyzer is unable to access ‘/var/log/rift/rift.log’ because permissions on ‘/var/log/rift’ are set to 600.  To resolve permissions issues, run: ‘chmod 755 /var/log/rift’.
