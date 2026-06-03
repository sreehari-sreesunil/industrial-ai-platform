import { createBrowserRouter } from "react-router-dom";

import DashboardLayout from "../layouts/DashboardLayout";

import HomePage from "../pages/HomePage";
import AssetsPage from "../pages/AssetsPage";
import AssetDetailsPage from "../pages/AssetDetailsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <DashboardLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: "assets",
        element: <AssetsPage />,
      },
      {
        path: "assets/:id",
        element: <AssetDetailsPage />,
      },
    ],
  },
]);