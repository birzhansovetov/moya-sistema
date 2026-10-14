import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import { Shell } from './components/Shell'
import { AuthPage } from './pages/Auth'
import { ProfilePage } from './pages/Profile'
import { TodayPage } from './pages/Today'
import { TasksPage } from './pages/Tasks'
import { CalendarPage } from './pages/Calendar'
import { SectionsPage } from './pages/Sections'
import { StudyPage } from './pages/Study'
import { EducationPage } from './pages/Education'
import { ReadingPage } from './pages/Reading'
import { PersonalPage } from './pages/Personal'
import { FinancePage } from './pages/Finance'
import { HealthPage } from './pages/Health'
import { SportPage } from './pages/Sport'
import { NutritionPage } from './pages/Nutrition'
import { OnboardingPage } from './pages/Onboarding'

export function App() {
  const { user, loading, setAuthenticated } = useAuth()
  if (loading) return <div className="loadingScreen">Открываем ваше пространство…</div>
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
      <Route path="education" element={<EducationPage />} />
      <Route path="education/java" element={<StudyPage key="java" courseId="java" />} />
      <Route path="education/go" element={<StudyPage key="go" courseId="go" />} />
      <Route path="languages" element={<StudyPage key="english" courseId="english" />} />
      <Route path="profession" element={<StudyPage key="java-backend" courseId="java-backend" />} />
      <Route path="education/reading" element={<ReadingPage />} />
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
