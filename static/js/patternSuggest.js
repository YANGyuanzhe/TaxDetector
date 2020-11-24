function PatternSuggest(i) {

    var svg = d3.select(".selectView")
        .append("svg")
        .attr("class", "patternSuggest")


    var simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(function(d) { return d.id; }))
        .force("charge", d3.forceManyBody())
        .force("x", d3.forceX())
        .force("y", d3.forceY())
        .force("center", d3.forceCenter(75, 75));
    $.getJSON("../static/data/suggestStruct.json", function(data) {
        graph = data[i]
        var root = svg.append("g")


        var link = root.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(graph.links)
            .enter().append("line")
            .attr("stroke-width", 3);

        var node = root.append("g")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .attr("class", "nodes")
            .selectAll("g")
            .data(graph.nodes)
            .enter().append("g")
        var circles = node.append("circle")
            .attr("r", 10)
            .attr("fill", "red")

        node.append("title")
            .text(function(d) { return d.id })
        simulation.nodes(graph.nodes)
            .on("tick", ticked);
        console.log(graph.links)
        console.log(graph.nodes)
        simulation.force("link")
            .links(graph.links)

        svg.on("click", function() {
            $.post("/postPatternSuggest", { graph })
        })

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
        }

    })

}

for (var i = 0; i < 4; i++) {
    PatternSuggest(i)
}