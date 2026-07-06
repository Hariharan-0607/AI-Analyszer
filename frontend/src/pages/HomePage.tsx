import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { analyzeSubmission, AnalyzeResponse } from '../api/client';

export function HomePage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [outcomes, setOutcomes] = useState('');
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!zipFile) {
      setError('Please select a ZIP file');
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('project_title', title);
    formData.append('project_description', description);
    formData.append('project_outcomes', outcomes);
    formData.append('zip_file', zipFile);
    formData.append('questions_per_skill', '2');

    try {
      const data = await analyzeSubmission(formData);
      setResult(data);
      sessionStorage.setItem('analysis_result', JSON.stringify(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const startViva = () => {
    if (result) {
      navigate(`/viva/${result.analysis_id}`);
    }
  };

  return (
    <div className="container">
      <h1>Project Submission AI Analyzer</h1>
      <p>Upload your project ZIP to analyze it and start a proctored viva.</p>

      <form onSubmit={handleSubmit} className="card">
        <label htmlFor="title">Project Title *</label>
        <input
          id="title"
          type="text"
          value={title}
          placeholder="e.g. FastAPI Todo CRUD"
          onChange={(e) => setTitle(e.target.value)}
          required
        />

        <label htmlFor="description">Project Description</label>
        <textarea
          id="description"
          value={description}
          placeholder="Briefly describe what your project does..."
          onChange={(e) => setDescription(e.target.value)}
        />

        <label htmlFor="outcomes">Project Outcomes *</label>
        <textarea
          id="outcomes"
          value={outcomes}
          placeholder={"1. Build a REST API with CRUD endpoints\n2. Use Python and FastAPI\n3. Validate requests with Pydantic\n4. Structure code into modules"}
          onChange={(e) => setOutcomes(e.target.value)}
          required
        />

        <label htmlFor="zip">ZIP File *</label>
        <input
          id="zip"
          type="file"
          accept=".zip"
          onChange={(e) => setZipFile(e.target.files?.[0] ?? null)}
          required
        />

        <div style={{ marginTop: 20 }}>
          <button type="submit" className="primary" disabled={loading}>
            {loading ? 'Analyzing...' : 'Analyze Submission'}
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {result && (
          <button type="button" className="primary" onClick={startViva} style={{ marginTop: 16 }}>
            Start Proctored Viva
          </button>
        )}
      </form>
    </div>
  );
}
