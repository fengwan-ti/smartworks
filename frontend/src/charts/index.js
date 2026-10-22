/**
 * ECharts 统一入口。
 * 约定：每个图表一个导出函数，返回 option 对象；颜色与字号在这里统一，页面里不写死。
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, GraphChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  MarkLineComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GraphChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  TitleComponent,
  DatasetComponent,
  MarkLineComponent,
  CanvasRenderer
])

export const CHART_COLORS = ['#1f3864', '#2d5aa0', '#4a90d9', '#7ab8e8', '#f0a13a', '#e05c5c']

/** 通用折线图配置 */
export function lineOption({ xData = [], series = [], title = '' } = {}) {
  return {
    title: { text: title, left: 'left', textStyle: { fontSize: 13, color: '#1f3864' } },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0, itemWidth: 12, itemHeight: 8, textStyle: { fontSize: 11 } },
    grid: { left: 48, right: 24, top: 44, bottom: 36 },
    xAxis: { type: 'category', data: xData, axisLine: { lineStyle: { color: '#ccc' } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#eee' } } },
    series: series.map((s, i) => ({
      type: 'line',
      smooth: true,
      showSymbol: false,
      itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
      ...s
    }))
  }
}

export default echarts
