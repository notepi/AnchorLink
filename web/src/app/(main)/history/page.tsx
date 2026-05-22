import { getQuantLabView } from '@/lib/quant-lab-reader';
import QuantLabTopBar from '@/components/quant-lab/QuantLabTopBar';
import StrategyHero from '@/components/quant-lab/StrategyHero';
import CompositeScoreEngine from '@/components/quant-lab/CompositeScoreEngine';
import StrategyCurve from '@/components/quant-lab/StrategyCurve';
import MeanReversionPanel from '@/components/quant-lab/MeanReversionPanel';
import SignalAlphaScatter from '@/components/quant-lab/SignalAlphaScatter';
import MLPanel from '@/components/quant-lab/MLPanel';
import PoolLinkagePanel from '@/components/quant-lab/PoolLinkagePanel';
import ScoreCalendar from '@/components/quant-lab/ScoreCalendar';
import SignalWeightTable from '@/components/quant-lab/SignalWeightTable';
import '../../../styles/quant-lab.css';

export default async function HistoryPage() {
  const view = await getQuantLabView();

  if (!view) {
    return (
      <div className="quant-lab">
        <div className="ql-error">
          量化实验室数据加载失败，请检查以下文件是否存在：
          <ul style={{ marginTop: 12, textAlign: 'left', display: 'inline-block' }}>
            <li>data/output/composite_signal_backtest.json</li>
            <li>data/output/history_deep_quant_analysis.json</li>
            <li>data/output/history_2nd_order_analysis.json</li>
          </ul>
        </div>
      </div>
    );
  }

  return (
    <div className="quant-lab">
      <QuantLabTopBar generatedAt={view.backtest.generatedAt} />
      <StrategyHero backtest={view.backtest} />
      <CompositeScoreEngine backtest={view.backtest} />
      <StrategyCurve daily={view.backtest.daily_results} />
      <MeanReversionPanel data={view.deepQuant.M_excessMeanReversion} />
      <SignalAlphaScatter signals={view.secondOrder.alphaSignalRank} />
      <MLPanel data={view.deepQuant.P_machineLearning} />
      <PoolLinkagePanel data={view.deepQuant.N_poolLinkage} />
      <ScoreCalendar daily={view.backtest.daily_results} />
      <SignalWeightTable weights={view.backtest.signal_weights} />

      <footer style={{ textAlign: 'center', padding: '20px 0', fontSize: 11, color: 'var(--ql-text-muted)' }}>
        ⚠️ 本页所有分析为历史统计描述，<strong>不构成投资建议</strong>。
        阈值使用 in-sample 数据，存在前视偏差。
      </footer>
    </div>
  );
}
