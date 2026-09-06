import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import ConsumptionOverview from './pages/ConsumptionOverview';
import Utilization from './pages/Utilization';
import Optimizations from './pages/Optimizations';
import { TeamProvider } from './contexts/TeamContext';

function App() {
  return (
    <TeamProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<ConsumptionOverview />} />
            <Route path="utilization" element={<Utilization />} />
            <Route path="optimizations" element={<Optimizations />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </TeamProvider>
  );
}

export default App;
