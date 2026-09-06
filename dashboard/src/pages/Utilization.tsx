import { useState, useEffect } from 'react';
import ChatPanel from '../components/ChatPanel';
import { MessageSquare, Server, Loader2 } from 'lucide-react';
import { useTeam } from '../contexts/TeamContext';
import axios from 'axios';

export default function Utilization() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { selectedTeam } = useTeam();
  const [resources, setResources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchResources = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`/api/utilization/resources?team=${selectedTeam}`);
        setResources(res.data);
      } catch (error) {
        console.error('Error fetching utilization', error);
      } finally {
        setLoading(false);
      }
    };
    fetchResources();
  }, [selectedTeam]);

  if (loading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-zinc-400" /></div>;
  }

  return (
    <div className="flex flex-col gap-6 relative">
      <div className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-sm">
        <div className="p-4 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-[#09090b]">
          <h3 className="font-semibold text-zinc-950 dark:text-zinc-50">Tracked Resources</h3>
        </div>
        <table className="w-full text-left text-sm">
          <thead className="bg-zinc-100 dark:bg-zinc-900 text-zinc-500 dark:text-zinc-400">
            <tr>
              <th className="px-6 py-3 font-medium">Resource Name</th>
              <th className="px-6 py-3 font-medium">Type</th>
              <th className="px-6 py-3 font-medium">Avg CPU</th>
              <th className="px-6 py-3 font-medium">Avg Memory</th>
              <th className="px-6 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800 text-zinc-900 dark:text-zinc-200">
            {resources.map(r => (
              <tr key={r.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/50 cursor-pointer transition-colors">
                <td className="px-6 py-4 flex items-center gap-2">
                  <Server className="w-4 h-4 text-zinc-400" />
                  <span className="font-medium">{r.name}</span>
                </td>
                <td className="px-6 py-4">{r.type}</td>
                <td className="px-6 py-4">{r.cpu}%</td>
                <td className="px-6 py-4">{r.memory}%</td>
                <td className="px-6 py-4">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    r.status === 'underused' 
                      ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-400' 
                      : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                  }`}>
                    {r.status}
                  </span>
                </td>
              </tr>
            ))}
            {resources.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-8 text-center text-zinc-500">No resources found for this team.</td>
              </tr>
            )}
          </tbody>
        </table>
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
        contextText={`User is looking at Utilization for ${selectedTeam}`} 
      />
    </div>
  );
}
