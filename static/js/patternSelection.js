var curNode = 0,
    patternNodes = [],
    patternEdges = [],
    nodesSelectedNumber = 0,
    nodesSelected = []

function PatternSelection() {


    var width = 350,
        height = 250

    const radius = 10

    function color(type) {
        switch (type) {
            case "taxpayer":
                return "#FFB6C1"
            case "legal person":
                return "#87CEFA"
            case "invest":
                return "#00FF00"
            case "control":
                return "#FFDD55"
            default:
                return black
        }
    }

    var svg = d3.select("#patternSvg")

    const marker1 = svg.append("marker")
        .attr("id", "arrow1")
        .attr("markerUnits", "strokeWidth") //设置为strokeWidth箭头会随着线的粗细发生变化
        .attr("viewBox", "0 0 12 12") //坐标系的区域
        .attr("refX", 15) //箭头坐标
        .attr("refY", 6)
        .attr("markerWidth", 12)
        .attr("markerHeight", 12)
        .attr("orient", "auto") //绘制方向，可设定为：auto（自动确认方向）和 角度值
        .append("path")
        .attr("d", "M2,2 L2,11 L10,6 L2,2") //箭头的路径
        .attr("fill", color('control'))
    const marker2 = svg.append("marker")
        .attr("id", "arrow2")
        .attr("markerUnits", "strokeWidth") //设置为strokeWidth箭头会随着线的粗细发生变化
        .attr("viewBox", "0 0 12 12") //坐标系的区域
        .attr("refX", 15) //箭头坐标
        .attr("refY", 6)
        .attr("markerWidth", 12)
        .attr("markerHeight", 12)
        .attr("orient", "auto") //绘制方向，可设定为：auto（自动确认方向）和 角度值
        .append("path")
        .attr("d", "M2,2 L2,11 L10,6 L2,2") //箭头的路径
        .attr("fill", color('invest'))


    function drawNode(color, position, nodeIndex) {
        svg.append('circle')
            .attr('cx', position[0])
            .attr('cy', position[1])
            .attr('r', radius)
            .attr('fill', color)
            .on("click", function(d) {
                d3.select(this).attr("r", "5")
                nodesSelectedNumber += 1
                nodesSelected.push(nodeIndex)
            })
            // .on("dblclick", function(d) {
            //     d3.select(this).remove()
            // })
    }

    function drawEdge(position1, position2, type) {
        svg.append('line')
            .attr('x1', position1[0])
            .attr('y1', position1[1])
            .attr('x2', position2[0])
            .attr('y2', position2[1])
            .attr('stroke-width', '2px')
            .attr("marker-end", type == 'control' ? "url(#arrow1)" : "url(#arrow2)")
            .attr('stroke', color(type))

    }

    function addNode(type) {
        var position = []
        svg.on("click", function() {
            position = d3.mouse(this)
            drawNode(color(type), position, curNode)
            patternNodes.push({ "id": curNode, "type": type, "position": position })
            curNode += 1
        })
        $.post("/postPatternNodes", { patternNodes })
    }

    function addEdge(type) {
        svg.on("click", null)
        if (nodesSelectedNumber == 2) {
            var source = patternNodes[nodesSelected[0]],
                target = patternNodes[nodesSelected[1]]
            patternEdges.push({ "source": source, "target": target, "type": type })
            d3.select("#patternSvg").selectAll("circle").attr("r", radius)
            drawEdge(source.position, target.position, type)
            nodesSelected = []
            nodesSelectedNumber = 0
        }
        $.post("/postPatternEdges", { patternEdges })
    }
    return {
        addNode: addNode,
        addEdge: addEdge
    }
}