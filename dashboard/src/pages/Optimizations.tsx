import { useState, useEffect } from 'react';
import ChatPanel from '../components/ChatPanel';
import { 
  MessageSquare, 
  ArrowRightCircle, 
  Loader2, 
  ShieldAlert, 
  Layers, 
  CheckCircle2, 
  RotateCcw, 
  Activity,
  X,
  AlertTriangle
} from 'lucide-react';
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

  // Individual Review & Sign-Off state
  const [reviewRec, setReviewRec] = useState<any | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [reviewerName, setReviewerName] = useState('platform-engineer');
  const [reviewNotes, setReviewNotes] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [isRejecting, setIsRejecting] = useState(false);

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

  const [approvingId, setApprovingId] = useState<string | null>(null);

  const handleIndividualSignOff = async (rec: any) => {
    console.log(`[FinOps] Mandatory Individual Review button clicked for: ${rec.resource} (ID: ${rec.id})`);
    console.log(`[FinOps] Dispatching POST /api/optimizations/${rec.id}/approve ...`);
    setApprovingId(rec.id);
    setActionMessage(null);
    try {
      const res = await axios.post(`/api/optimizations/${rec.id}/approve`, {
        reviewer: 'platform-engineer',
        notes: `Mandatory individual review sign-off completed for ${rec.resource} (${rec.autonomy_tier || 'tier_2'})`,
      });
      console.log(`[FinOps] Individual sign-off successfully approved:`, res.data);
      setActionMessage(`Successfully approved ${rec.resource} via mandatory individual review sign-off!`);
      await fetchRecs();
    } catch (err: any) {
      console.error(`[FinOps] Failed to approve recommendation:`, err);
      setActionMessage(err.response?.data?.error || 'Failed to approve recommendation.');
    } finally {
      setApprovingId(null);
    }
  };

  const handleApprove = async (recId: string) => {
    setReviewing(true);
    setActionMessage(null);
    try {
      console.log(`[FinOps] Modal sign-off approve initiated for ID: ${recId}`);
      const res = await axios.post(`/api/optimizations/${recId}/approve`, {
        notes: reviewNotes || 'Approved via individual sign-off review.',
        reviewer: reviewerName || 'platform-engineer',
      });
      console.log(`[FinOps] Modal sign-off response:`, res.data);
      setActionMessage(`Successfully approved recommendation for ${reviewRec?.resource || recId} with individual sign-off!`);
      setReviewRec(null);
      setReviewNotes('');
      await fetchRecs();
    } catch (err: any) {
      console.error(`[FinOps] Modal approval failed:`, err);
      setActionMessage(err.response?.data?.error || 'Failed to approve recommendation.');
    } finally {
      setReviewing(false);
    }
  };

  const handleReject = async (recId: string) => {
    setReviewing(true);
    setActionMessage(null);
    try {
      console.log(`[FinOps] Modal rejection initiated for ID: ${recId}`);
      const res = await axios.post(`/api/optimizations/${recId}/reject`, {
        reason: rejectReason || 'Rejected during individual review.',
        reviewer: reviewerName || 'platform-engineer',
      });
      console.log(`[FinOps] Modal rejection response:`, res.data);
      setActionMessage(`Recommendation for ${reviewRec?.resource || recId} was rejected.`);
      setReviewRec(null);
      setRejectReason('');
      setIsRejecting(false);
      await fetchRecs();
    } catch (err: any) {
      console.error(`[FinOps] Modal rejection failed:`, err);
      setActionMessage(err.response?.data?.error || 'Failed to reject recommendation.');
    } finally {
      setReviewing(false);
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
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 whitespace-nowrap cursor-pointer"
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
                  className="mt-6 w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium bg-rose-600 hover:bg-rose-700 text-white transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
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
                <div className="mt-6 flex flex-col gap-2">
                  <button 
                    onClick={() => handleIndividualSignOff(rec)}
                    disabled={isApproved || approvingId === rec.id}
                    className={`w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 font-medium transition-colors shadow-sm disabled:cursor-not-allowed ${
                      isApproved 
                        ? 'bg-zinc-200 dark:bg-zinc-800 text-zinc-500 cursor-not-allowed'
                        : isTier1
                          ? 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer'
                          : 'bg-amber-600 hover:bg-amber-700 text-white cursor-pointer'
                    }`}
                  >
                    {approvingId === rec.id ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Processing Sign-off...
                      </>
                    ) : isApproved ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                        Approved
                      </>
                    ) : isTier1 ? (
                      <>
                        Review & Approve
                        <ArrowRightCircle className="w-4 h-4" />
                      </>
                    ) : (
                      <>
                        Mandatory Individual Review
                        <ArrowRightCircle className="w-4 h-4" />
                      </>
                    )}
                  </button>

                  {!isApproved && (
                    <button
                      type="button"
                      onClick={() => {
                        console.log('[FinOps] Opening blast-radius details modal for:', rec.resource);
                        setReviewRec(rec);
                        setIsRejecting(false);
                        setReviewNotes('');
                        setRejectReason('');
                      }}
                      className="text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 text-center underline cursor-pointer"
                    >
                      Inspect Blast-Radius Details & Sign-Off Notes
                    </button>
                  )}
                </div>
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

      {/* Individual Review & Sign-Off Modal */}
      {reviewRec && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
          <div className="bg-white dark:bg-[#0c0c0f] border border-zinc-200 dark:border-zinc-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl flex flex-col gap-5 my-8">
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  {reviewRec.autonomy_tier === 'tier_2' ? (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                      <ShieldAlert className="w-3.5 h-3.5" /> Tier 2 (Mandatory Individual Sign-off)
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                      <Layers className="w-3.5 h-3.5" /> Tier 1 (Low Blast-Radius)
                    </span>
                  )}
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    Scope: <span className="font-medium text-zinc-700 dark:text-zinc-300">{reviewRec.team}</span>
                  </span>
                </div>
                <h3 className="text-lg font-bold text-zinc-950 dark:text-zinc-50">
                  {reviewRec.autonomy_tier === 'tier_2' ? 'Mandatory Individual Review' : 'Recommendation Review & Approval'}
                </h3>
              </div>
              <button
                onClick={() => setReviewRec(null)}
                className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 p-1 rounded-md hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Warning banner for Tier 2 */}
            {reviewRec.autonomy_tier === 'tier_2' ? (
              <div className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-xl p-3.5 flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-900 dark:text-amber-200 space-y-1">
                  <p className="font-semibold">Human-in-the-Loop Safety Gate Triggered</p>
                  <p>
                    Autonomous execution and batch approvals are strictly blocked for this resource. An authorized engineer must inspect the blast-radius triggers and SRE verification before explicit sign-off.
                  </p>
                </div>
              </div>
            ) : (
              <div className="bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 rounded-xl p-3.5 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-900 dark:text-emerald-200">
                  <p className="font-semibold">Low Blast-Radius Action</p>
                  <p>This action is within safe operational thresholds. You can sign-off individually now.</p>
                </div>
              </div>
            )}

            {/* Target & Financial Impact */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3">
                <span className="text-[11px] uppercase tracking-wider text-zinc-500 dark:text-zinc-400 block font-medium">Est. Savings</span>
                <span className="text-emerald-600 dark:text-emerald-400 font-bold text-lg">${reviewRec.savings}<span className="text-xs font-normal">/mo</span></span>
              </div>
              <div className="bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3">
                <span className="text-[11px] uppercase tracking-wider text-zinc-500 dark:text-zinc-400 block font-medium">Action</span>
                <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm">{reviewRec.recommendation_type || 'rightsize'}</span>
              </div>
              <div className="bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3">
                <span className="text-[11px] uppercase tracking-wider text-zinc-500 dark:text-zinc-400 block font-medium">Current SKU</span>
                <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm truncate block" title={reviewRec.current_state?.current_sku || reviewRec.current_state?.sku || 'n2-standard-16'}>
                  {reviewRec.current_state?.current_sku || reviewRec.current_state?.sku || 'n2-standard-16'}
                </span>
              </div>
              <div className="bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3">
                <span className="text-[11px] uppercase tracking-wider text-zinc-500 dark:text-zinc-400 block font-medium">Proposed SKU</span>
                <span className="font-semibold text-zinc-900 dark:text-zinc-100 text-sm truncate block" title={reviewRec.proposed_state?.sku || reviewRec.proposed_state?.target_sku || 'n2-standard-4'}>
                  {reviewRec.proposed_state?.sku || reviewRec.proposed_state?.target_sku || 'n2-standard-4'}
                </span>
              </div>
            </div>

            {/* Target Resource */}
            <div className="text-xs bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-200 dark:border-zinc-800 rounded-xl p-3">
              <span className="text-zinc-500 dark:text-zinc-400 block font-medium mb-1">Target Resource:</span>
              <code className="text-zinc-900 dark:text-zinc-200 font-mono break-all">{reviewRec.resource}</code>
            </div>

            {/* Blast Radius & SRE Evaluation */}
            <div className="space-y-2">
              <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">Blast Radius Assessment:</span>
              <div className="flex flex-wrap gap-1.5">
                {reviewRec.reasons?.map((reason: string, idx: number) => (
                  <span key={idx} className="px-2 py-1 rounded-md text-xs bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
                    {reason}
                  </span>
                ))}
              </div>
            </div>

            {/* Sign-off Form */}
            <div className="space-y-3 pt-2 border-t border-zinc-200 dark:border-zinc-800">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">Reviewer Identity</label>
                  <input
                    type="text"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    className="w-full text-xs px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g. platform-engineer"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300 mb-1">
                    {isRejecting ? 'Rejection Reason' : 'Sign-Off Notes / Approval Scope'}
                  </label>
                  {isRejecting ? (
                    <input
                      type="text"
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      className="w-full text-xs px-3 py-2 rounded-lg border border-rose-300 dark:border-rose-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-rose-500"
                      placeholder="e.g. Workload peak expected next week"
                    />
                  ) : (
                    <input
                      type="text"
                      value={reviewNotes}
                      onChange={(e) => setReviewNotes(e.target.value)}
                      className="w-full text-xs px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
                      placeholder="e.g. SRE verified headroom; safe for change window"
                    />
                  )}
                </div>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-zinc-200 dark:border-zinc-800">
              <button
                type="button"
                onClick={() => setIsRejecting(!isRejecting)}
                className="text-xs text-rose-600 dark:text-rose-400 hover:underline font-medium cursor-pointer"
              >
                {isRejecting ? 'Switch to Sign-off / Approval' : 'Need to reject this recommendation?'}
              </button>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <button
                  type="button"
                  onClick={() => setReviewRec(null)}
                  className="px-4 py-2 text-xs font-medium rounded-lg text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                {isRejecting ? (
                  <button
                    type="button"
                    disabled={reviewing}
                    onClick={() => handleReject(reviewRec.id)}
                    className="flex items-center gap-2 bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
                  >
                    {reviewing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    Confirm Rejection
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={reviewing}
                    onClick={() => handleApprove(reviewRec.id)}
                    className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-5 py-2 rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
                  >
                    {reviewing ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                    Sign-off & Approve
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setIsChatOpen(true)}
        className="fixed bottom-8 right-8 p-4 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-xl transition-transform hover:scale-105 z-40 cursor-pointer"
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
