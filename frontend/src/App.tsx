import { useProfileId } from "./hooks/useProfileId";
import ProfilePicker from "./components/ProfilePicker";
import ProductGrid from "./components/ProductGrid";

export default function App() {
  const { profileId, setProfileId } = useProfileId();

  if (!profileId) {
    return <ProfilePicker onPicked={(p) => setProfileId(p.id)} />;
  }

  return (
    <ProductGrid
      profileId={profileId}
      onSwitchProfile={() => setProfileId(null)}
    />
  );
}
