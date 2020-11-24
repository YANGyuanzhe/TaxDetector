function MainView() {

    var svg = d3.select("#mainSvg"),
        width = +svg.attr("width"),
        height = +svg.attr("height");
    // svg objects

    function color(group) {
        return group == "Movie" ? "#1F77B4" : (group == "Director" ? "#2DA02D" : "#FF7F0F");
    }

    var simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(function(d) { return d.id; }))
        .force("charge", d3.forceManyBody())
        .force("x", d3.forceX())
        .force("y", d3.forceY())
        .force("center", d3.forceCenter(550, 400));
    // load the data
    $.get("/getMainViewData", function(graph) {
        var root = svg.append("g");
        console.log(graph.nodes)
        console.log("root is", root)

        var link = root.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graph.links)
            .enter().append("line")
            .attr("stroke-width", function(d) { return Math.sqrt(d.value); });

        var node = root.append("g")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .attr("class", "nodes")
            .selectAll("g")
            .data(graph.nodes)
            .enter().append("g")
            .on("click", clickNode)
            .on("mouseover", focus)
            .on("mouseout", unfocus);


        var circles = node.append("circle")
            .attr("r", function(d) { return (d.group == "Movie") ? 10 : 5; })
            .attr("fill", function(d) { return color(d.group); })
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        node.append("title")
            .text(function(d) { return d.id; });

        var texts = root.selectAll(".texts")
            .data(graph.nodes)
            .enter()
            .append("text")
            .attr("dx", 12)
            .attr("dy", "0.35em")
            .attr("visibility", "hidden")
            .text(d => d.id);

        var legend_data = [
            { text: "M", color: "#1F77B4" },
            { text: "D", color: "#2DA02D" },
            { text: "A", color: "#FF7F0F" }
        ];

        const legend = root
            .append('g')
            .attr('class', 'legend')
            .attr('transform', `translate(0,0)`)
            .selectAll('g')
            .data(legend_data)
            .enter()
            .append('g')
            .attr('transform', function(d, i) {
                return 'translate(' + (10) + ',' + (10 + (25 * i)) + ')';
            });
        legend
            .append('rect')
            .attr('width', 20)
            .attr('height', 20)
            .style('fill', (d, i) => d.color);
        legend
            .append('text')
            .text(d => d.text)
            .attr('x', 25)
            .attr('y', 25 / 2)
            .attr('dy', 4);

        simulation.nodes(graph.nodes)
            .on("tick", ticked);
        console.log("aa")
        console.log(graph.links)
        simulation.force("link")
            .links(graph.links);
        console.log("b")
        const zoom = d3.zoom();

        zoom.on("zoom", () => {
            const { transform } = d3.event;
            root.attr("transform", transform);
        });

        svg.call(zoom).call(zoom.transform, d3.zoomIdentity);

        const reset = () => {
            svg.transition()
                .duration(750)
                .call(zoom.transform, d3.zoomIdentity);
        }

        var nodeLinkStatus = {};
        graph.links.forEach(d => {
            nodeLinkStatus[`${d.source.index},${d.target.index}`] = 1;
        });

        function isConnected(a, b) {
            return nodeLinkStatus[`${a.index},${b.index}`] || nodeLinkStatus[`${b.index},${a.index}`] || a.index === b.index;
        }

        function focus(d) {
            node.style('stroke-opacity', o => (isConnected(d, o) ? 1 : 0.3))
                .style('fill-opacity', o => (isConnected(d, o) ? 1 : 0.3));

            texts.style("visibility", o => (isConnected(d, o) ? "visible" : "hidden"));

            link.style('opacity', function(l) {
                return (d === l.source || d === l.target) ? 1 : 0.2;
            });

            link.style('stroke-width', function(l) {
                return (d === l.source || d === l.target) ? 5 : 1;
            });
        }

        function unfocus(d) {
            node.style('stroke-opacity', 1)
                .style('fill-opacity', 1);
            link.style('opacity', 1);
            link.style('stroke-width', 1);
            texts.style("visibility", "hidden");

        }

        function ticked() {
            link
                .attr("x1", function(d) { return d.source.x; })
                .attr("y1", function(d) { return d.source.y; })
                .attr("x2", function(d) { return d.target.x; })
                .attr("y2", function(d) { return d.target.y; });

            node
                .attr("transform", function(d) {
                    return "translate(" + d.x + "," + d.y + ")";
                })

            texts
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }

    });


    function dragstarted(d) {
        if (!d3.event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(d) {
        d.fx = d3.event.x;
        d.fy = d3.event.y;
    }

    function dragended(d) {
        if (!d3.event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    function mouseOver(node) {
        d3.select(this).select("circle")
            .transition()
            .duration(500)
            .attr("r", 20);
    }

    function mouseOut(node) {
        d3.select(this).select("circle")
            .transition()
            .duration(500)
            .attr("r", (node.group == "Movie") ? 10 : 5);
    }

    function clickNode(node) {
        console.log("click")
        var myChart1 = echarts.init(document.getElementById('lineView1'))
        var myChart2 = echarts.init(document.getElementById('lineView2'))
        $.getJSON('../static/data/bj.json', function(data) {
            myChart1.setOption(option = {
                title: {
                    text: 'detail view'
                },
                xAxis: {
                    data: data.map(function(item) {
                        return item[0];
                    })
                },
                yAxis: {
                    splitLine: {
                        show: false
                    }
                },
                dataZoom: [{
                    startValue: '2014-06-01'
                }, {
                    type: 'inside'
                }],
                series: {
                    name: 'Beijing AQI',
                    type: 'line',
                    data: data.map(function(item) {
                        return item[1];
                    }),
                    markLine: {
                        silent: true,
                        data: [{
                            yAxis: 50
                        }, {
                            yAxis: 100
                        }, {
                            yAxis: 150
                        }, {
                            yAxis: 200
                        }, {
                            yAxis: 300
                        }]
                    }
                }
            });
        });

        myChart2.setOption(option = {
            xAxis: {
                type: 'category',
                data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            },
            yAxis: {
                type: 'value'
            },
            series: [{
                data: [120, 200, 150, 80, 70, 110, 130],
                type: 'bar',
                showBackground: true,
                backgroundStyle: {
                    color: 'rgba(220, 220, 220, 0.8)'
                }
            }]
        })
    }
}
MainView()