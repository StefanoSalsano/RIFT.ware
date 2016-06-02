#!/bin/bash

DEMO_DIR=$RIFT_INSTALL/demos
CORE_UTIL_DIR=$RIFT_INSTALL/usr/rift/systemtest/util

wait_system=1000

system_cmd="${DEMO_DIR}/mgmt_tbed.py"

up_cmd="${CORE_UTIL_DIR}/wait_until_system_started.py --max-wait $wait_system"

instance_id_file="/var/rift/env.d/RWVM_INSTANCE_ID"

if [ -f ${instance_id_file} ]
then
  read vm_instance_id < ${instance_id_file}
else
  echo "$0: error ${instance_id_file} not found"
  exit 1
fi

rpc_cmd="agent-tests all continue-on-failure false"
result_file="${RIFT_MODULE_TEST}/mgmtagt_test_result.txt"
test_cmd="$RIFT_INSTALL/usr/bin/zsh --rwmsg -c '${rpc_cmd}' > ${result_file}"

${CORE_UTIL_DIR}/systest_wrapper.sh --system_cmd "$system_cmd" --up_cmd "$up_cmd" --test_cmd "$test_cmd"

# Save the exit code from systest_wrapper.sh
rc=$?

# Return the saved exit code
exit $rc
