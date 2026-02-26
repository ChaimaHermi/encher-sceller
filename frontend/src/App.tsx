import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Home } from './pages/Home';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { BuyerCatalog } from './pages/BuyerCatalog';
import { SellerDashboard } from './pages/SellerDashboard';
import { SellerUpload } from './pages/SellerUpload';
import { ListingDetail } from './pages/ListingDetail';
import { Auction } from './pages/Auction';
import './App.css';

function App() {
  return (
    <ThemeProvider>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="login" element={<Login />} />
            <Route path="register" element={<Register />} />
            <Route
              path="buyer/catalog"
              element={
                <ProtectedRoute requireRole="buyer">
                  <BuyerCatalog />
                </ProtectedRoute>
              }
            />
            <Route
              path="seller/dashboard"
              element={
                <ProtectedRoute requireRole="seller">
                  <SellerDashboard />
                </ProtectedRoute>
              }
            />
            <Route
              path="seller/upload"
              element={
                <ProtectedRoute requireRole="seller">
                  <SellerUpload />
                </ProtectedRoute>
              }
            />
            <Route
              path="listing/:listingId"
              element={
                <ProtectedRoute>
                  <ListingDetail />
                </ProtectedRoute>
              }
            />
            <Route path="auction/:address" element={<Auction />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
