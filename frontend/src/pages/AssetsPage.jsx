import { useEffect, useState } from "react";

import { getAssets } from "../api/assets";

import AssetCard from "../components/AssetCard";

function AssetsPage() {
  const [assets, setAssets] = useState([]);

  useEffect(() => {
    async function fetchAssets() {
      try {
        const data = await getAssets();

        setAssets(data);
      } catch (error) {
        console.error(error);
      }
    }

    fetchAssets();
  }, []);

  return (
    <div>
      <h1>Assets</h1>

      {assets.map((asset) => (
        <AssetCard
          key={asset.id}
          asset={asset}
        />
      ))}
    </div>
  );
}

export default AssetsPage;