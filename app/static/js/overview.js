const graphElement = document.getElementById("keyword-graph");
const graphEmpty = document.getElementById("graph-empty");

if (graphElement && window.echarts) {
  fetch(`/api/keywords/graph${window.location.search}`)
    .then((response) => response.json())
    .then((data) => {
      if (!data.nodes.length) {
        graphElement.classList.add("hidden");
        graphEmpty.classList.remove("hidden");
        return;
      }
      const chart = echarts.init(graphElement);
      chart.setOption({
        tooltip: { formatter: "{b}: {c} 篇论文" },
        series: [{
          type: "graph", layout: "force", roam: true, label: { show: true },
          force: { repulsion: 180, edgeLength: 90 },
          data: data.nodes.map((node) => ({ ...node, symbolSize: 24 + node.value * 9 })),
          links: data.links,
        }],
      });
      chart.on("click", (event) => {
        const params = new URLSearchParams(window.location.search);
        params.set("keyword", event.data.name);
        window.location.href = `/papers?${params.toString()}`;
      });
    })
    .catch(() => {
      graphElement.classList.add("hidden");
      graphEmpty.textContent = "图谱加载失败，请使用热门方向列表继续查看论文。";
      graphEmpty.classList.remove("hidden");
    });
}
