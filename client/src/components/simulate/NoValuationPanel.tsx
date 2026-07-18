import { Link } from 'react-router';
import EmptyState from '../ui/EmptyState';

interface NoValuationPanelProps {
  playerId: number;
  playerName: string | null;
}

/** The 409 player_without_value state: nothing honest to project from. */
export default function NoValuationPanel({ playerId, playerName }: NoValuationPanelProps) {
  return (
    <EmptyState
      heading="No market valuation on record"
      body={`Precedent anchors every projection to the player's current market value — ${
        playerName ?? 'this player'
      } has none in the dataset, so there's nothing honest to project from.`}
      action={
        <Link
          to={`/players/${playerId}`}
          className="rounded border border-pitch-800 bg-pitch-900 px-4 py-2 text-sm text-ink-100 hover:border-yale-400"
        >
          ← Back to profile
        </Link>
      }
    />
  );
}
