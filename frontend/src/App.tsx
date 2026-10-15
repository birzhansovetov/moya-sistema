import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Button } from './components/ui'
import { useAuth } from './auth'
import { Shell } from './components/Shell'
import { AuthPage } from './pages/Auth'
import { ProfilePage } from './pages/Profile'
import { TodayPage } from './pages/Today'
import { TasksPage } from './pages/Tasks'
import { CalendarPage } from './pages/Calendar'
import { SectionsPage } from './pages/Sections'
import { StudyPage } from './pages/Study'
import { ProfessionPage } from './pages/Profession'
import { legacyDestination } from './navigation'
import { ReadingPage } from './pages/Reading'
import { PersonalPage } from './pages/Personal'
import { FinancePage } from './pages/Finance'
import { HealthPage } from './pages/Health'
import { SportPage } from './pages/Sport'
import { NutritionPage } from './pages/Nutrition'
import { OnboardingPage } from './pages/Onboarding'
import { LanguagesPage } from './pages/Languages'
import { useParams } from 'react-router-dom'

function LegacyRoute(){const {pathname,search,hash}=useLocation();return <Navigate replace to={legacyDestination(pathname,search,hash)||'/profession'}/>}
function ProfessionRoute(){const {search}=useLocation();return new URLSearchParams(search).has('plan')?<LegacyRoute/>:<ProfessionPage/>}
function LanguageRoute() {
  const { courseId } = useParams()
  return ['english', 'kazakh', 'korean', 'turkish', 'spanish'].includes(courseId || '')
    ? <StudyPage key={courseId} courseId={courseId!} /> : <Navigate to="/languages" replace />
}

export function App() {
  const { user, loading, sessionError, retrySession, setAuthenticated } = useAuth()
  const { pathname } = useLocation()
  const publicAuthPage = ['/login', '/register', '/forgot-password', '/verify-email', '/reset-password'].includes(pathname)
  if (!publicAuthPage && loading) return <div className="loadingScreen" role="status">Открываем ваше пространство…</div>
  if (!publicAuthPage && sessionError && !user) return <main className="sessionRecovery">
    <h1>Не удалось загрузить пространство</h1>
    <p role="alert">{sessionError}</p>
    <Button onClick={retrySession}>Повторить загрузку</Button>
    <Link to="/login">Перейти ко входу</Link>
  </main>
  return <Routes>
    <Route path="/login" element={user ? <Navigate to="/" replace /> : <AuthPage onAuthenticated={setAuthenticated} />} />
    <Route path="/register" element={user ? <Navigate to="/" replace /> : <AuthPage onAuthenticated={setAuthenticated} />} />
    <Route path="/forgot-password" element={<AuthPage onAuthenticated={setAuthenticated} />} />
    <Route path="/verify-email" element={<AuthPage onAuthenticated={setAuthenticated} />} />
    <Route path="/reset-password" element={<AuthPage onAuthenticated={setAuthenticated} />} />
    <Route path="/onboarding" element={user ? <OnboardingPage /> : <Navigate to="/login" replace />} />
    <Route element={user ? user.onboarding_complete === false ? <Navigate to="/onboarding" replace /> : <Shell /> : <Navigate to="/login" replace />}>
      <Route index element={<TodayPage />} />
      <Route path="sections" element={<SectionsPage />} />
      <Route path="education" element={<LegacyRoute />} />
      <Route path="books" element={<ReadingPage />} />
      <Route path="education/java" element={<LegacyRoute />} />
      <Route path="education/go" element={<LegacyRoute />} />
      <Route path="languages" element={<LanguagesPage />} />
      <Route path="languages/:courseId" element={<LanguageRoute />} />
      <Route path="profession" element={<ProfessionRoute />} />
      <Route path="profession/java" element={<StudyPage key="java" courseId="java" />} />
      <Route path="profession/go" element={<StudyPage key="go" courseId="go" />} />
      <Route path="profession/backend" element={<StudyPage key="java-backend" courseId="java-backend" />} />
      <Route path="education/reading" element={<LegacyRoute />} />
      <Route path="personal" element={<PersonalPage />} />
      <Route path="finance" element={<FinancePage />} />
      <Route path="health" element={<HealthPage />} />
      <Route path="health/sport" element={<SportPage />} />
      <Route path="health/nutrition" element={<NutritionPage />} />
      <Route path="health/calories" element={<NutritionPage view="calculator" />} />
      <Route path="tasks" element={<TasksPage />} />
      <Route path="calendar" element={<CalendarPage />} />
      <Route path="profile" element={<ProfilePage />} />
    </Route>
    <Route path="*" element={<Navigate to={user ? '/' : '/login'} replace />} />
  </Routes>
}
