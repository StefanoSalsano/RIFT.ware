
/*
 * 
 * (c) Copyright RIFT.io, 2013-2016, All Rights Reserved
 *
 */
import React from 'react';
import d3 from 'd3';
import DashboardCard from '../dashboard_card/dashboard_card.jsx';

// Use for the debugger panel
import Button from '../button/rw.button.js';


export default class TopologyL2Graph extends React.Component {
    constructor(props) {
        super(props);
        this.data = props.data;
        this.iteration = 0;
        this.selectedID = 0;
        this.nodeCount = 0;
        this.network_coding = {};
        this.nodeEvent = props.nodeEvent || null;
    }

    componentDidMount(){
        var weight = 400;
        var handler = this;
        this.force = d3.layout.force()
            .size([this.props.width, this.props.height])
            .charge(-weight)
            .linkDistance(weight)
            .on("tick", this.tick.bind(this));

        this.drag = this.force.drag()
            .on("dragstart", function(d) {
                handler.dragstart(d, handler);
        });

        this.svg = d3.select(React.findDOMNode(this.refs.topologyL2)).append("svg")
            .attr("width", this.props.width)
            .attr("height", this.props.height)
            .classed("topology", true);
    }

    componentWillUnmount() {
        if (this.do_remove_hack) {
            d3.select('svg').remove();
        } else {

        }
    }

    componentWillReceiveProps(props) {
        if (props.data.links.length > 0) {
            if (this.props.static_mode) {
                this.svg.selectAll('*').remove();
            }

            this.network_coding = this.create_group_coding(props.data.network_ids.sort());
            this.update(props.data);
        }
        this.iteration++;
    }

    create_group_coding(group_ids) {
        var group_coding = {};
        group_ids.forEach(function(element, index, array) {
            group_coding[element] = index+1;
        });
        return group_coding;
    }

    getNetworkCoding(network_id) {
        var group = this.network_coding[network_id];
        if (group != undefined) {
            return group;
        } else {
            return 0;
        }
    }

    drawLegend(graph) {
        // Hack to prevent multiple legends being displayed
        this.svg.selectAll(".legend").remove();

        var showBox = false;
        var svg = this.svg;
        var item_count = (graph.network_ids) ? graph.network_ids.length : 0;
        var pos = {
            anchorX: 5,
            anchorY: 5,
            height: 40,
            width: 200,
            items_y: 35,
            items_x: 7,
            item_height: 25
        };
        pos.height += item_count * pos.item_height;
        var legend_translate = "translate("+pos.anchorX+","+pos.anchorY+")";

        var legend = svg.append("g")
            .attr("class", "legend")
            .attr("transform", legend_translate);

        var legend_box = (showBox) ? legend.append("rect")
                .attr("x", 0)
                .attr("y", 0)
                .attr("height", pos.height)
                .attr("width", pos.width)
                .style("stroke", "black")
                .style("fill", "none") : null;

        legend.append("text")
            .attr("x", 5)
            .attr("y", 15)
            .text("Network color mapping:");

        legend.selectAll("g").data(graph.network_ids)
            .enter()
            .append("g")
            .each(function(d, i) {
                var colors = ["green", "orange", "red" ];
                var g = d3.select(this);
                var group_number = i+1;
                g.attr('class', "node-group-" + group_number);

                g.append("circle")
                    .attr("cx", pos.items_x + 3)
                    .attr("cy", pos.items_y + i * pos.item_height)
                    .attr("r", 6);

                g.append("text")
                    .attr("x", pos.items_x + 25)
                    .attr("y", pos.items_y + (i * pos.item_height + 4))
                    .attr("height", 20)
                    .attr("width", 80)
                    .text(d);
            })
    }

    update(graph) {
        var svg = this.svg;
        var handler = this;

        this.force
            .nodes(graph.nodes)
            .links(graph.links)
            .start();

        this.link = svg.selectAll(".link")
            .data(graph.links)
            .enter().append("line")
                .attr("class", "link");

        this.gnodes = svg.selectAll('g.gnode')
            .data(graph.nodes)
            .enter()
            .append('g')
            .classed('gnode', true)
            .attr('data-network', function(d) { return d.network; })
            .attr('class', function(d) {
                return d3.select(this).attr('class') + ' node-group-'+ handler.getNetworkCoding(d.network);
            });

        this.node = this.gnodes.append("circle")
            .attr("class", "node")
            .attr("r", this.props.radius)
            .on("dblclick", function(d) {
                handler.dblclick(d, handler)
            })
            .on("click", function(d) {
                handler.click.call(this, d, handler)
            })
            .call(this.drag);
        var labels = this.gnodes.append("text")
            .attr("text-anchor", "middle")
            .attr("fill", "black")
            .attr("font-size", "12")
            .attr("y", "-10")
            .text(function(d) { return d.name; });
        this.drawLegend(graph);
    }

    tick = () => {
        this.link.attr("x1", function(d) { return d.source.x; })
               .attr("y1", function(d) { return d.source.y; })
               .attr("x2", function(d) { return d.target.x; })
               .attr("y2", function(d) { return d.target.y; });

        this.gnodes.attr("transform", function(d) {
            return 'translate(' + [d.x, d.y] + ')';
        });

    }

    click(d, topo) {
        // 'This' is the svg circle element
        var gnode = d3.select(this.parentNode);

        topo.svg.selectAll("text").transition()
            .duration(topo.props.nodeText.transitionTime)
            .attr("font-size", topo.props.nodeText.size)
            .attr("fill", topo.props.nodeText.color)

        // Set focus node text properties
        d3.select(this.parentNode).selectAll('text').transition()
            .duration(topo.props.nodeText.transitionTime)
            .attr("font-size", topo.props.nodeText.focus.size)
            .attr("fill", topo.props.nodeText.focus.color);

        // Perform detail view
        topo.selectedID = d.id;
        if (topo.nodeEvent) {
            topo.nodeEvent(d.id);
        }
        // set record view as listener
    }

    dblclick(d, topo) {
        d3.select(this).classed("fixed", d.fixed = false);
    }

    dragstart (d) {
        //console.log('dragstart called. d=', d);
        // Causes node.getAttribute is not a function error
        // Remarked out for now
        //d3.select(this).classed("fixed", d.fixed = true);
    }

    render() {
        return ( 
            <DashboardCard showHeader={true} title="Topology L2 Graph"
                headerExtras={this.props.headerExtras} >
            {
                (this.props.debugMode)
                    ? <TopologyGraphDebugPanel showMe={true} topoClass={this}/>
                    : false
            }

              <div ref="topologyL2"></div>
            </DashboardCard>
        )
    }
}

TopologyL2Graph.propTypes = {
    debugMode: React.PropTypes.bool
}

TopologyL2Graph.defaultProps = {
    width: 800,
    height: 600,
    maxLabel: 150,
    duration: 500,
    radius: 6,
    data: {
        nodes: [],
        links: [],
        network_ids: []
    },
    nodeText: {
        size: 12,
        color: 'black',
        focus: {
            size: 14,
            color: 'blue'
        },
        transitionTime: 250
    },
    debugMode: false
}


class TopologyGraphDebugPanel extends React.Component {
    constructor(props) {
        super(props);
    }
    handleForceToggle() {
        console.log("handleForceToggle called");

    }
    render() {
        if (!this.props.showMe) {
            return (<div></div>);
        } else {
            return (
                <div className="topologyGraphDebugPanel">
                    <span>Topology Graph Debugger</span>
                    <Button label="Stop Force" className="forceToggle"
                        onClick={this.handleForceToggle} />
                </div>
            );
        }

    }
}

