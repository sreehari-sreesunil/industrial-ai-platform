import { Link } from "react-router-dom";

function AssetCard({ asset }) {
  return (
    <Link
      to={`/assets/${asset.id}`}
      style={{
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <div
        style={{
          border: "1px solid #ccc",
          padding: "1rem",
          marginBottom: "1rem",
          borderRadius: "8px",
          cursor: "pointer",
        }}
      >
        <h3>{asset.name}</h3>

        <p>ID: {asset.id}</p>
      </div>
    </Link>
  );
}

export default AssetCard;