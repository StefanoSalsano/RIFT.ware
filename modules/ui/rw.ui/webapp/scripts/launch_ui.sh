#!/bin/bash

# 
# (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
#

server_pid=0

usage() {
	echo "usage: launch_ui.sh [--enable-https --keyfile-path=<keyfile_path> --certfile-path=<certfile-path>]"
}

function handle_received_signal() {
    forever stopall && kill -9 $server_pid 2>/dev/null
    wait $server_pid
    echo "Terminated web server PID: $server_pid"
    exit
}


start_servers() {
	cd $THIS_DIR
	echo "Killing any previous instance of server_rw.ui_ui.py"
	for ui_pid in $(ps -ef | awk '/[s]scripts\/server_rw.ui_ui.py/{print $2}'); do
		kill -9 ${ui_pid} 2>/dev/null
	done
	echo "Stopping any previous instance of forever"
	forever stopall

	echo "Running Python webserver. HTTPS Enabled: ${ENABLE_HTTPS}"
	cd ../public
	if [ ! -z "${ENABLE_HTTPS}" ]; then
		../scripts/server_rw.ui_ui.py --enable-https --keyfile-path="${KEYFILE_PATH}" --certfile-path="${CERTFILE_PATH}"&
		server_pid=$!
	else
		../scripts/server_rw.ui_ui.py&
		server_pid=$!
	fi

	echo "Running Node.js API server. HTTPS Enabled: ${ENABLE_HTTPS}"
	cd ../../api
	if [ ! -z "${ENABLE_HTTPS}" ]; then
		forever start -a -l forever.log -o out.log -e err.log server.js	--enable-https --keyfile-path="${KEYFILE_PATH}" --certfile-path="${CERTFILE_PATH}"
	else
		forever start -a -l forever.log -o out.log -e err.log server.js
	fi
}


# Begin work
for i in "$@"
do
case $i in
    -k=*|--keyfile-path=*)
    KEYFILE_PATH="${i#*=}"
    shift # past argument=value
    ;;
    -c=*|--certfile-path=*)
    CERTFILE_PATH="${i#*=}"
    shift # past argument=value
    ;;
    -h|--help)
    usage
    exit
    ;;
    -e|--enable-https)
    ENABLE_HTTPS=YES
    shift # past argument=value
    ;;
    *)
        # unknown option
    ;;
esac
done

if [[ ! -z "${ENABLE_HTTPS}" ]]; then
	if [ -z "${KEYFILE_PATH}" ] || [ -z "{CERTFILE_PATH}" ]; then
		usage
		exit
	fi
fi


# change to the directory of this script
THIS_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

# Call function to start web and API servers
start_servers


# Ensure that the forever script is stopped when this script exits
trap "echo \"Received EXIT\"; handle_received_signal" EXIT
trap "echo \"Received SIGINT\"; handle_received_signal" SIGINT
trap "echo \"Received SIGKILL\"; handle_received_signal" SIGKILL
trap "echo \"Received SIGABRT\"; handle_received_signal" SIGABRT
trap "echo \"Received SIGQUIT\"; handle_received_signal" SIGQUIT
trap "echo \"Received SIGSTOP\"; handle_received_signal" SIGSTOP
trap "echo \"Received SIGTERM\"; handle_received_signal" SIGTERM
trap "echo \"Received SIGTRAP\"; handle_received_signal" SIGTRAP

# Keep this script in the foreground so the system doesn't think that the
# server crashed.
while true; do
  sleep 5
done
