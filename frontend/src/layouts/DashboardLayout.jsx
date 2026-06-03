import { Link, Outlet } from "react-router-dom";

function DashboardLayout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        style={{
          width: "220px",
          padding: "1rem",
          borderRight: "1px solid #ccc",
        }}
      >
        <h2>Industrial AI</h2>

        <nav
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem",
            marginTop: "2rem",
          }}
        >
          <Link to="/">Home</Link>
          <Link to="/assets">Assets</Link>
        </nav>
      </aside>

      <main style={{ flex: 1, padding: "2rem" }}>
        <Outlet />
      </main>
    </div>
  );
}

export default DashboardLayout;