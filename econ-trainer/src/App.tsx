import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout.tsx'
import { Glossary } from './pages/Glossary.tsx'
import { Home } from './pages/Home.tsx'
import { Progress } from './pages/Progress.tsx'
import { Quiz } from './pages/Quiz.tsx'
import { Study } from './pages/Study.tsx'
import { AppStateProvider } from './state/AppStateContext.tsx'

export default function App() {
  return (
    <AppStateProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/study" element={<Study />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/glossary" element={<Glossary />} />
            <Route path="/progress" element={<Progress />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AppStateProvider>
  )
}
