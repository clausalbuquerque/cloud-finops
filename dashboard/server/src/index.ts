import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { Pool } from 'pg';
import { spawn } from 'child_process';

dotenv.config();

const app = express();
const port = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'cloud_finops',
  password: process.env.DB_PASSWORD || 'postgres123',
  port: parseInt(process.env.DB_PORT || '5433', 10),
});

// Helper for building where clause
const getTeamWhere = (team: any, column: string = "tags->>'team'") => {
  if (team && team !== 'all') {
    return `WHERE ${column} = $1`;
  }
  return '';
};
const getTeamParam = (team: any) => {
  return team && team !== 'all' ? [team] : [];
};

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

app.get('/api/consumption/summary', async (req, res) => {
  try {
    const { team } = req.query;
    const where = getTeamWhere(team);
    const params = getTeamParam(team);
    const result = await pool.query(
      `SELECT COALESCE(SUM(effective_cost), 0) as total_spend FROM finops.consumption_records ${where}`,
      params
    );
    res.json({
      totalSpend: parseFloat(result.rows[0].total_spend).toLocaleString('en-US', { style: 'currency', currency: 'USD' }),
      monthOverMonthChange: team === 'data-platform' ? '↑ 12.4%' : '↓ 5.2%', // Mocked change percentage
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/consumption/trends', async (req, res) => {
  try {
    const { team } = req.query;
    const where = getTeamWhere(team);
    const params = getTeamParam(team);
    // Group by usage_date and service_category (Mocking compute/storage using service_category)
    const result = await pool.query(
      `SELECT usage_date, service_category, SUM(effective_cost) as cost 
       FROM finops.consumption_records 
       ${where} 
       GROUP BY usage_date, service_category 
       ORDER BY usage_date ASC`,
      params
    );
    
    // Format for ECharts
    const dates = [...new Set(result.rows.map(r => new Date(r.usage_date).toLocaleDateString()))];
    
    // Group by category
    const computeData = new Array(dates.length).fill(0);
    const storageData = new Array(dates.length).fill(0);
    
    result.rows.forEach(row => {
      const dateIdx = dates.indexOf(new Date(row.usage_date).toLocaleDateString());
      if (dateIdx !== -1) {
        const cost = parseFloat(row.cost);
        if (row.service_category?.toLowerCase().includes('storage')) {
          storageData[dateIdx] += cost;
        } else {
          computeData[dateIdx] += cost;
        }
      }
    });

    res.json({ dates, compute: computeData, storage: storageData });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/utilization/resources', async (req, res) => {
  try {
    // For now we mock the result to match the frontend shape but in reality we'd join finops.tracked_resources
    // We'll return a mocked list that can be filtered on the frontend for speed
    res.json([
      { id: 'vm-1', name: 'analytics-worker-01', team: 'data-platform', type: 'Compute', cpu: 12, memory: 45, status: 'underused' },
      { id: 'vm-2', name: 'web-frontend-prod', team: 'core-services', type: 'Compute', cpu: 65, memory: 70, status: 'healthy' },
      { id: 'db-1', name: 'users-db-main', team: 'core-services', type: 'Database', cpu: 8, memory: 20, status: 'underused' },
      { id: 'k8s-1', name: 'platform-cluster-01', team: 'data-platform', type: 'Container', cpu: 45, memory: 85, status: 'healthy' },
      { id: 'vm-3', name: 'ml-training-node', team: 'marketing-ai', type: 'Compute', cpu: 95, memory: 90, status: 'healthy' },
    ]);
  } catch (error) {
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/optimizations', async (req, res) => {
  try {
    const { team } = req.query;
    const where = getTeamWhere(team, 'scope_team');
    const params = getTeamParam(team);
    
    const result = await pool.query(
      `SELECT id, resource_id, scope_team, recommendation_type, proposed_state, estimated_monthly_savings, sre_assessment, status 
       FROM finops.optimization_recommendations ${where}`,
      params
    );
    
    const mapped = result.rows.map(r => {
      const savings = parseFloat(r.estimated_monthly_savings) || 0;
      const resId = (r.resource_id || '').toLowerCase();
      const sreAssessment = r.sre_assessment || {};
      const blastRadius = sreAssessment.blast_radius || {};

      // Deterministic blast-radius & autonomy classification
      const isProduction = blastRadius.is_production ?? (resId.includes('prod') || (r.scope_team || '').toLowerCase().includes('prod'));
      const isStateful = blastRadius.is_stateful ?? (resId.includes('db') || resId.includes('sql') || resId.includes('storage'));
      const isSharedOrCritical = blastRadius.is_shared_or_critical ?? (resId.includes('cluster') || resId.includes('k8s') || resId.includes('lb'));
      const isHighSpend = savings >= 50.0;

      const isTier2 = isProduction || isStateful || isSharedOrCritical || isHighSpend;
      const autonomyTier = isTier2 ? 'tier_2' : 'tier_1';
      const tierName = isTier2 ? 'Tier 2 (Mandatory Individual Sign-off)' : 'Tier 1 (Autonomous / Batched Review)';
      const canBeBatched = !isTier2;

      const reasons: string[] = [];
      if (isProduction) reasons.push('Production environment');
      if (isStateful) reasons.push('Stateful database/storage');
      if (isSharedOrCritical) reasons.push('Shared cluster/backend');
      if (isHighSpend) reasons.push(`High spend ($${savings.toFixed(2)}/mo >= $50)`);
      if (reasons.length === 0) reasons.push('Non-prod, stateless, low-spend (< $50/mo)');

      return {
        id: r.id,
        resource: r.resource_id,
        team: r.scope_team,
        action: `${r.recommendation_type} -> ${r.proposed_state?.sku || 'Review'}`,
        savings: savings.toFixed(2),
        status: r.status,
        autonomy_tier: autonomyTier,
        tier_name: tierName,
        can_be_batched: canBeBatched,
        requires_individual_signoff: isTier2,
        reasons,
        blast_radius: {
          tier: autonomyTier,
          tier_name: tierName,
          can_be_batched: canBeBatched,
          is_production: isProduction,
          is_stateful: isStateful,
          is_shared_or_critical: isSharedOrCritical,
          is_high_spend: isHighSpend,
          financial_impact_usd: savings,
          reasons,
        }
      };
    });
    
    res.json(mapped);
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/optimizations/batch-approve', async (req, res) => {
  try {
    const { ids } = req.body;
    if (!Array.isArray(ids) || ids.length === 0) {
      return res.status(400).json({ error: 'ids array is required' });
    }

    const items = await pool.query(
      `SELECT id, resource_id, estimated_monthly_savings FROM finops.optimization_recommendations WHERE id = ANY($1)`,
      [ids]
    );

    const blockedItems: string[] = [];
    for (const r of items.rows) {
      const savings = parseFloat(r.estimated_monthly_savings) || 0;
      const resId = (r.resource_id || '').toLowerCase();
      if (resId.includes('prod') || resId.includes('db') || savings >= 50.0) {
        blockedItems.push(r.resource_id);
      }
    }

    if (blockedItems.length > 0) {
      return res.status(400).json({
        error: `Cannot batch approve Tier 2 items. Mandatory individual sign-off required for: ${blockedItems.join(', ')}`
      });
    }

    await pool.query(
      `UPDATE finops.optimization_recommendations SET status = 'approved', updated_at = NOW() WHERE id = ANY($1)`,
      [ids]
    );

    res.json({ status: 'ok', approved_count: ids.length });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/optimizations/:id/rollback', async (req, res) => {
  try {
    const { id } = req.params;
    const { reason, initiated_by } = req.body || {};

    const itemRes = await pool.query(
      `SELECT id, resource_id, current_state, proposed_state, status, provider_name FROM finops.optimization_recommendations WHERE id = $1`,
      [id]
    );

    if (itemRes.rows.length === 0) {
      return res.status(404).json({ error: `Recommendation with ID '${id}' not found` });
    }

    const rec = itemRes.rows[0];
    if (rec.status !== 'executed') {
      return res.status(400).json({
        error: `Cannot rollback recommendation '${id}'. Current status is '${rec.status}', must be 'executed'.`
      });
    }

    const baselineSku = rec.current_state?.current_sku || rec.current_state?.sku || 'n2-standard-16';
    const rollbackReason = reason || 'Performance degradation detected during canary observation window.';
    const rollbackCmd = `gcloud compute instances set-machine-type ${rec.resource_id.split('/').pop()} --machine-type=${baselineSku}`;

    await pool.query(
      `UPDATE finops.optimization_recommendations 
       SET status = 'rolled_back', 
           actual_monthly_savings = 0.0, 
           rejection_reason = $1, 
           updated_at = NOW() 
       WHERE id = $2`,
      [`Rolled back: ${rollbackReason}`, id]
    );

    res.json({
      status: 'rolled_back',
      recommendation_id: id,
      resource_id: rec.resource_id,
      restored_sku: baselineSku,
      rollback_command: rollbackCmd,
      reason: rollbackReason,
      rolled_back_by: initiated_by || 'user_console',
      rolled_back_at: new Date().toISOString(),
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.get('/api/optimizations/:id/canary', async (req, res) => {
  try {
    const { id } = req.params;
    const itemRes = await pool.query(
      `SELECT id, resource_id, current_state, proposed_state, status, updated_at FROM finops.optimization_recommendations WHERE id = $1`,
      [id]
    );

    if (itemRes.rows.length === 0) {
      return res.status(404).json({ error: `Recommendation with ID '${id}' not found` });
    }

    const rec = itemRes.rows[0];
    const isExecuted = rec.status === 'executed';
    const isRolledBack = rec.status === 'rolled_back';

    const elapsedMinutes = Math.min(60, Math.max(0, Math.floor((Date.now() - new Date(rec.updated_at).getTime()) / 60000)));
    const remainingMinutes = Math.max(0, 60 - elapsedMinutes);
    const canaryStatus = isRolledBack ? 'rolled_back' : isExecuted ? (remainingMinutes > 0 ? 'active' : 'healthy') : 'inactive';

    res.json({
      recommendation_id: id,
      resource_id: rec.resource_id,
      baseline_sku: rec.current_state?.current_sku || 'n2-standard-16',
      target_sku: rec.proposed_state?.target_sku || 'n2-standard-8',
      status: canaryStatus,
      duration_minutes: 60,
      elapsed_minutes: elapsedMinutes,
      remaining_minutes: remainingMinutes,
      canary_active: isExecuted && remainingMinutes > 0,
    });
  } catch (error) {
    console.error(error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.post('/api/chat', async (req, res) => {
  const { message, team } = req.body;
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  try {
    const response = await fetch('http://localhost:8000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query: message, team: team || 'data-platform' })
    });

    if (!response.body) throw new Error("No response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      res.write(chunk);
    }

    res.write(`data: [DONE]\n\n`);
    res.end();
  } catch (err) {
    console.error('Failed to proxy to Python agent:', err);
    res.write(`data: ${JSON.stringify({ type: 'FINAL_RESPONSE', content: 'Error: Failed to connect to the agent engine at port 8000. Is FastAPI running?' })}\n\n`);
    res.write(`data: [DONE]\n\n`);
    res.end();
  }
});

app.listen(port, () => {
  console.log(`BFF Server running at http://localhost:${port}`);
});
