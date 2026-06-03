import { useParams } from "react-router-dom";

function AssetDetailsPage() {
  const { id } = useParams();

  return (
    <div>
      <h1>Asset Details</h1>

      <p>Asset ID: {id}</p>
    </div>
  );
}

export default AssetDetailsPage;