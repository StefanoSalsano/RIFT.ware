RIFT.ware
=========

### RIFT.ware version 4.2.1 Release Notes
Updated May 27, 2016

RIFT.ware version 4.2.1 resources are available at http://repo.riftio.com/releases/open.riftio.com/4.2.1/

To enable the intel-4.2.1 yum repository, run the following command in the Launchpad VM:
`curl -o /etc/yum.repos.d/riftware-4.2-intel_4.2.1.repo http://repo.riftio.com/releases/repos/intel_4.2.1.repo`


Read the documentation at https://open.riftio.com/webdocs/RIFTware-4.2/

Visit https://support.riftio.com to post questions or raise issues.


## Fixed Issues
* RIFT-10949  After starting a new RW.CLI session, you can safely ignore the message, "Error: failed to add cli mode: node”, as long as the rift-shell prompt ("rift#") is also received.
* RIFT-11416  The RIFT.ware Launchpad Composer page is missing links for About, Debug, and Log.


## Known Issues
* IRIO-51  Update fails on an existing account without deleting and re-adding it. An update operation is supported only if the cloud account is not in use. Workaround: If the account is being used (for example, you have already instantiated one or more network services associated with that cloud account), remove the account and add it again with the new account details.
* IRIO-52  Exporting an NSD failed.
* RIFT-11095  An image exported from the RIFT.ware UI does not include the type of NFV object in its name, such as VNFD or NSD.
* RIFT-11010  On the Launchpad interface, descriptors cannot be deleted on the Catalog page. Workaround: Either refresh the Catalog page or navigate to the Launchpad Dashboard and back to the Catalog to remove a descriptor.
* RIFT-11507  Onboarding a malformed ping_vnfd package (with incorrect checksum.txt content) succeeds when it should fail with error.
* RIFT-11508  Onboarding a malformed ping_vnfd package (with incorrect checksum.txt value) succeeds when it should fail with error.
* RIFT-12354  The Launchpad interface fails to return a message when cloud accounts are created with invalid information.
* RIFT-12460  Launchpad should support updates of Cloud/SDN/Config Agent accounts.
* RIFT-11300  After element `<vnfd:internal-connection-point-ref>` is removed from an, otherwise, valid descriptor (ping_vnfd.xml), the onboarding step incorrectly succeeds. This element is an internal reference for the VNFD. The omission is discovered during network service instantiation only.
* RIFT-11305  Adding an unknown attribute to the ping-pong VNF descriptors and network descriptor (ping_vnfd.xml, ping_pong_nsd.xml) causes an onboard failure.
* RIFT-13287  Deleting and recreating the same OpenStack account causes an exception.
* RIFT-11488  After starting the network service and terminating the ping VM from the OpenStack dashboard, the system fails to report that the ping VM has been terminated.
* RIFT-11489  The RIFT.ware Launchpad fails to detect that a virtual link between ping_vnfd and pong_vnfd has been deleted.

In 4.1.1, if the operator tries to use the Logs feature, LogAnalyzer is unable to access '/var/log/rift/rift.log' because permissions on '/var/log/rift' are set to 600.  To resolve permissions issues, run: `chmod 755 /var/log/rift`.

