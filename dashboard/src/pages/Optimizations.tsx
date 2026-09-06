import { useState, useEffect } from 'react';
import ChatPanel from '../components/ChatPanel';
import { MessageSquare, ArrowRightCircle, Loader2, ShieldAlert, Layers, CheckCircle2, RotateCcw, Activity } from 'lucide-react';
import { useTeam } from '../contexts/TeamContext';
import axios from 'axios';

export default function Optimizations() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const { selectedTeam } = useTeam();
  const [recs, setRecs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [batching, setBatching] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const fetchRecs = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`/api/optimizations?team=${selectedTeam}`);
      setRecs(res.data);
    } catch (error) {
      console.error('Error fetching optimizations', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecs();
  }, [selectedTeam]);

  const tier1Recs = recs.filter(r => r.autonomy_tier === 'tier_1' && r.status !== 'approved' && r.status !== 'executed' && r.status !== 'rolled_back');

  const handleBatchApprove = async () => {
    if (tier1Recs.length === 0) return;
    setBatching(true);
    setActionMessage(null);
    try {
      const ids = tier1Recs.map(r => r.id);
      await axios.post('/api/optimizations/batch-approve', { ids });
      setActionMessage(`Successfully approved ${ids.length} Tier 1 recommendations in batch!`);
      await fetchRecs();
    } catch (err: any) {
      setActionMessage(err.response?.data?.error || 'Failed to batch approve.');
    } finally {
      setBatching(false);
    }
  };

  const handleRollback = async (recId: string) => {
    setRollingBack(recId);
    setActionMessage(null);
    try {
      const res = await axios.post(`/api/optimizations/${recId}/rollback`, {
        reason: 'Manual 1-click rollback triggered from dashboard audit view.',
        initiated_by: 'dashboard_user',
      });
      setActionMessage(`Successfully rolled back recommendation! Restored baseline SKU: ${res.data.restored_sku}`);
      await fetchRecs();
    } catch (err: any) {
      setActionMessage(err.response?.data?.error || 'Failed to trigger rollback.');
    } finally {
      setRollingBack(null);
    }
  };

  if (loading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="w-8 h-8 animate-spin text-zinc-400" /></div>;
  }

  return (
    <div className="flex flex-col gap-6 relative">
      {/* Tiered Autonomy Batch Banner */}
      {tier1Recs.length > 0 && (
        <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 rounded-xl p-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-900/50 rounded-lg text-emerald-700 dark:text-emerald-300">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h4 className="font-semibold text-emerald-950 dark:text-emerald-200">
                Tier 1 Batched Review Available ({tier1Recs.length} actions)
              </h4>
              <p className="text-xs text-emerald-700 dark:text-emerald-400">
                Low blast-radius actions in non-production environments with &lt;$50/mo savings can be safely approved together.
              </p>
            </div>
          </div>
          <button
            onClick={handleBatchApprove}
            disabled={batching}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 whitespace-nowrap"
          >
            {batching ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            Batch Approve Tier 1 ({tier1Recs.length})
          </button>
        </div>
      )}

      {actionMessage && (
        <div className="bg-zinc-100 dark:bg-zinc-900 border border-zinc-300 dark:border-zinc-700 rounded-lg p-3 text-xs text-zinc-800 dark:text-zinc-200">
          {actionMessage}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {recs.map(rec => {
          const isTier1 = rec.autonomy_tier === 'tier_1';
          const isApproved = rec.status === 'approved';
          const isExecuted = rec.status === 'executed';
          const isRolledBack = rec.status === 'rolled_back';

          return (
            <div key={rec.id} className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-semibold text-zinc-950 dark:text-zinc-50">{rec.resource}</h3>
                  <span className="text-emerald-600 dark:text-emerald-400 font-bold tracking-tight text-lg">
                    ${rec.savings}/mo
                  </span>
                </div>

                {/* Autonomy Tier & Canary Badges */}
                <div className="flex flex-wrap items-center gap-2 mb-4">
                  {isTier1 ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      <Layers className="w-3.5 h-3.5" /> Tier 1 (Batched Review)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                      <ShieldAlert className="w-3.5 h-3.5" /> Tier 2 (Mandatory Individual Sign-off)
                    </span>
                  )}
                  {isApproved && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
                      <CheckCircle2 className="w-3 h-3" /> Approved
                    </span>
                  )}
                  {isExecuted && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-100 dark:bg-indigo-950 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800 animate-pulse">
                      <Activity className="w-3.5 h-3.5" /> Canary Active (60m window)
                    </span>
                  )}
                  {isRolledBack && (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
                      <RotateCcw className="w-3.5 h-3.5" /> Rolled Back to Baseline
                    </span>
                  )}
                </div>

                <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-2">
                  Action: <span className="font-medium text-zinc-900 dark:text-zinc-200">{rec.action}</span>
                </p>

                {/* Blast Radius Reasons */}
                {rec.reasons && rec.reasons.length > 0 && (
                  <div className="text-xs text-zinc-500 dark:text-zinc-400 bg-zinc-50 dark:bg-zinc-900/50 p-2.5 rounded-lg border border-zinc-100 dark:border-zinc-800/80">
                    <span className="font-medium text-zinc-700 dark:text-zinc-300">Blast Radius Triggers:</span> {rec.reasons.join(', ')}
                  </div>
                )}
              </div>

              {/* Action / Rollback Buttons */}
              {isExecuted ? (
                <button 
                  onClick={() => handleRollback(rec.id)}
                  disabled={rollingBack === rec.id}
                  className="mt-6 w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium bg-rose-600 hover:bg-rose-700 text-white transition-colors shadow-sm disabled:opacity-50"
                >
                  {rollingBack === rec.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                  1-Click Rollback to Baseline
                </button>
              ) : isRolledBack ? (
                <button 
                  disabled
                  className="mt-6 w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium bg-zinc-200 dark:bg-zinc-800 text-zinc-500 cursor-not-allowed shadow-sm"
                >
                  <RotateCcw className="w-4 h-4" /> Rolled Back to Baseline
                </button>
              ) : (
                <button 
                  disabled={isApproved}
                  className={`mt-6 w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors shadow-sm ${
                    isApproved 
                      ? 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500 cursor-not-allowed'
                      : isTier1
                        ? 'bg-emerald-600 hover:bg-emerald-700 text-white'
                        : 'bg-amber-600 hover:bg-amber-700 text-white'
                  }`}
                >
                  {isApproved ? 'Approved' : isTier1 ? 'Review & Approve' : 'Mandatory Individual Review'}{' '}
                  {!isApproved && <ArrowRightCircle className="w-4 h-4" />}
                </button>
              )}
            </div>
          );
        })}
        {recs.length === 0 && (
          <div className="col-span-full py-12 text-center text-zinc-500">
            No optimization recommendations for this team.
          </div>
        )}
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
        contextText={`User is looking at Optimizations for ${selectedTeam}`} 
      />
    </div>
  );
}
