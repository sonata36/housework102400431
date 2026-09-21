const trendElement = document.getElementById("trend-chart");
const statusElement = document.getElementById("trend-status");
let trendChart;
let playbackTimer;
let paused = false;

function queryTrend() {
  const keyword = document.getElementById("trend-keyword").value;
  const conferences = [...document.getElementById("trend-conferences").selectedOptions].map((option) => option.value).join(",");
  const years = document.getElementById("trend-years").value;
  return fetch(`/api/trends?keyword=${encodeURIComponent(keyword)}&conferences=${encodeURIComponent(conferences)}&years=${encodeURIComponent(years)}`).then((response) => response.json());
}

function drawTrend(data, limit) {
  const years = limit ? data.years.slice(0, limit) : data.years;
  trendChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: data.series.map((item) => item.name) },
    xAxis: { type: "category", data: years, name: "年份" },
    yAxis: { type: "value", name: "覆盖率 (%)" },
    series: data.series.map((item) => ({ name: item.name, type: "line", connectNulls: false, data: item.data.slice(0, years.length).map((point) => point.value) })),
  }, true);
  const labels = data.series.flatMap((item) => item.data).filter((point) => point.status !== "ok").map((point) => `${point.year} ${point.label}`);
  statusElement.textContent = labels.length ? `状态说明：${[...new Set(labels)].join("；")}` : "状态说明：当前显示范围均有可用数据。";
}

function loadTrend() {
  clearInterval(playbackTimer);
  queryTrend().then((data) => drawTrend(data));
}

function replayTrend() {
  clearInterval(playbackTimer);
  paused = false;
  queryTrend().then((data) => {
    let position = 1;
    drawTrend(data, position);
    playbackTimer = setInterval(() => {
      if (paused) return;
      position += 1;
      drawTrend(data, position);
      if (position >= data.years.length) clearInterval(playbackTimer);
    }, 650);
  });
}

function pauseTrend() {
  paused = !paused;
  document.getElementById("pause-trend").textContent = paused ? "继续" : "暂停";
}

if (trendElement && window.echarts) {
  trendChart = echarts.init(trendElement);
  document.getElementById("load-trend").addEventListener("click", loadTrend);
  document.getElementById("replay-trend").addEventListener("click", replayTrend);
  document.getElementById("pause-trend").addEventListener("click", pauseTrend);
  loadTrend();
}
