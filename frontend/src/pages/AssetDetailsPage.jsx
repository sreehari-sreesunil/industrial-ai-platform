import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getAssetById } from "../api/assets";

function AssetDetailsPage() {
  const { id } = useParams();

  const [asset, setAsset] = useState(null);

  useEffect(() => {
    async function fetchAsset() {
      try {
        const data = await getAssetById(id);

        setAsset(data);
      } catch (error) {
        console.error(error);
      }
    }

    fetchAsset();
  }, [id]);

  if (!asset) {
    return <p>Loading asset...</p>;
  }

  return (
    <div>
      <h1>{asset.name}</h1>

      <p>ID: {asset.id}</p>
    </div>
  );
}

export default AssetDetailsPage;