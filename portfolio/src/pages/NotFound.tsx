import { Link } from "react-router-dom";

export function NotFound() {
  return (
    <div className="space-y-3 py-16 text-center">
      <h1 className="text-3xl font-bold text-white">Page not found</h1>
      <Link to="/" className="text-indigo-300 underline">Back to home</Link>
    </div>
  );
}
