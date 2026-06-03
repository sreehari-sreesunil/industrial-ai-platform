import { createBrowserRouter } from "react-router-dom";

import HomePage from "../pages/HomePage";
import AssetsPage from "../pages/AssetsPage";
import AssetDetailsPage from "../pages/AssetDetailsPage";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <HomePage />,
  },
  {
    path: "/assets",
    element: <AssetsPage />,
  },
  {
    path: "/assets/:id",
    element: <AssetDetailsPage />,
  },
]);