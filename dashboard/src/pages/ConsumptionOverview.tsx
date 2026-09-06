import { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import ChatPanel from '../components/ChatPanel';
import { MessageSquare, Loader2 } from 'lucide-react';
import { useTeam } from '../contexts/TeamContext';
import axios from 'axios';

export default function ConsumptionOverview() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { selectedTeam } = useTeam();
  
  const [summary, setSummary] = useState({ totalSpend: '$0', change: '0%' });
  const [trendData, setTrendData] = useState({ dates: [], compute: [], storage: [] });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [summaryRes, trendsRes] = await Promise.all([
          axios.get(`/api/consumption/summary?team=${selectedTeam}`),
          axios.get(`/api/consumption/trends?team=${selectedTeam}`)
        ]);
        setSummary({
          totalSpend: summaryRes.data.totalSpend,
          change: summaryRes.data.monthOverMonthChange
        });
        setTrendData(trendsRes.data);
      } catch (error) {
        console.error('Error fetching data', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [selectedTeam]);

  const option = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trendData.dates,
      axisLine: { lineStyle: { color: '#71717a' } }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#71717a' } },
      splitLine: { lineStyle: { color: '#27272a' } }
    },
    series: [
      {
        name: 'Compute',
        type: 'line',
        stack: 'Total',
        areaStyle: {},
        emphasis: { focus: 'series' },
        data: trendData.compute,
        itemStyle: { color: '#3b82f6' }
      },
      {
        name: 'Storage',
        type: 'line',
        stack: 'Total',
        areaStyle: {},
        emphasis: { focus: 'series' },
        data: trendData.storage,
        itemStyle: { color: '#10b981' }
      }
    ]
  };

  if (loading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-zinc-400" /></div>;
  }

  return (
    <div className="flex flex-col gap-6 relative">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
          <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Total Spend (Mtd)</h3>
          <p className="text-3xl font-extrabold text-zinc-950 dark:text-zinc-50 mt-2">{summary.totalSpend}</p>
          <div className={`inline-flex items-center mt-2 px-2 py-0.5 rounded-full text-xs font-medium ${summary.change.includes('↓') ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' : 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400'}`}>
            {summary.change}
          </div>
        </div>
      </div>

      <div className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm">
        <h3 className="text-lg font-semibold text-zinc-950 dark:text-zinc-50 mb-4">Spend Trend</h3>
        <ReactECharts option={option} style={{ height: 400 }} theme="dark" />
      </div>

      <button
        onClick={() => setIsChatOpen(true)}
        className="fixed bottom-8 right-8 p-4 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-xl transition-transform hover:scale-105 z-40"
      >
        <MessageSquare className="w-6 h-6" />
      </button>

      <ChatPanel 
        isOpen={isChatOpen} 
        onClose={() => setIsChatOpen(false)} 
        contextText={`User is looking at Consumption Overview. Current Team: ${selectedTeam}`}
      />
    </div>
  );
}
