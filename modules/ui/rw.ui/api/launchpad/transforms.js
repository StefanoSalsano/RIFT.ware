
var _ = require('lodash');

function terminationPointValues (node) {
    var tpids = [];
    var attrs = { 'tp-id': [] };
    var TERM_PT_KEY = 'ietf-network-topology:termination-point';
    var TERM_PT_ATTR_KEY = 'ietf-l2-topology:l2-termination-point-attributes';

    var node_id = node['node-id'];
    node[TERM_PT_KEY].forEach(
        function(elem, index, array) {
            if ('tp-id' in elem) {
                attrs['tp-id'].push(elem['tp-id'])
            }
            if (TERM_PT_ATTR_KEY in elem) {
                for (var key in elem[TERM_PT_ATTR_KEY]) {
                    if (!(key in attrs)) {
                        attrs[key] = _.cloneDeep(elem[TERM_PT_ATTR_KEY][key]);
                    }
                }
            }
        });
    return {
        'node-id': node_id,
        attrs: attrs
    }
}

// Transforms one or more topologies into a collection of nodes, links
// usable by D3.js
function transformNetworkTopology(raw) {
    var nodes = [];
    var links = [];

    var y = 0;
    var id = 1;

    var node_mapper = {};
    var network_ids = [];

    var networks = raw;
    if ('collection' in raw) {
        networks = raw.collection;
    }
    if ('ietf-network:network' in networks) {
        networks = networks['ietf-network:network'];
    }

    // for each network in the array of networks
    for (var net_index=0, tot_networks=networks.length; net_index < tot_networks; net_index++) {
        var network = networks[net_index];
        var network_id = networks[net_index]['network-id'];
        if (network_ids.indexOf(network_id) == -1) {
            network_ids.push(network_id);
        }
        var raw_nodes = network['node'];
        var x = 0;
        for (var index=0, tot=raw_nodes.length; index < tot; index++) {
            var termination_point = [];
            var new_node = {
                id: id,
                // TODO: make short name, 
                name: raw_nodes[index]['node-id'],
                full_name: raw_nodes[index]['node-id'],
                network: network_id,
                x: x,
                y: y,
                attr: terminationPointValues(raw_nodes[index]).attrs
            };
            nodes.push(new_node);
            // What do wse do if the name is already collected
            node_mapper[new_node.name] = nodes.length-1;
            x += 20;
            id++;
        }

        var raw_links = network['ietf-network-topology:link'];
        if (raw_links) {
            for (var index=0, tot=raw_links.length; index < tot; index++) {
                var source_name = raw_links[index]['source']['source-node'];
                var dest_name = raw_links[index]['destination']['dest-node'];
                var new_link = {
                    source: node_mapper[source_name],
                    target: node_mapper[dest_name]
                };
                links.push(new_link);
            }
        }
        // prep for next network
        y += 20;
    }

    // D3 is expecting array indexes of the nodes for the links
    // Now for the links to find the nodes

    return {
        nodes: nodes,
        links: links,
        network_ids: network_ids
    };
}


module.exports = {
    transformNetworkTopology: transformNetworkTopology
}
