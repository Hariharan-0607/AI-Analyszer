import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { VivaPage } from './pages/VivaPage';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/viva/:analysisId" element={<VivaPage />} />
      </Routes>
    </BrowserRouter>
  );
}
