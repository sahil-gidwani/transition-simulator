import { Link } from 'react-router';
import { secondaryAction } from '../ui/actions';
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
        <Link to={`/players/${playerId}`} className={secondaryAction}>
          ← Back to profile
        </Link>
      }
    />
  );
}
