import React from 'react';
import { createBrowserRouter } from 'react-router-dom';

import DashboardLayout from '../layouts/DashboardLayout.jsx';

import HomePage from '../pages/HomePage.jsx';
import AssetsPage from '../pages/AssetsPage.jsx';
import AssetDetailsPage from '../pages/AssetDetailsPage.jsx';
import MetadataRegistryPage from '../pages/MetadataRegistryPage.jsx';
import LoginPage from '../pages/LoginPage.jsx';
import ProtectedRoute from "../components/ProtectedRoute";

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
 {
  path: '/',
  element: (
    <ProtectedRoute>
      <DashboardLayout />
    </ProtectedRoute>
  ),
  children: [
      {
        path: '',
        element: <HomePage />,
      },
      {
        path: 'assets',
        element: <AssetsPage />,
      },
      {
        path: 'assets/:id',
        element: <AssetDetailsPage />,
      },
      {
        path: 'registry',
        element: <MetadataRegistryPage />,
      },
    ],
  },
]);