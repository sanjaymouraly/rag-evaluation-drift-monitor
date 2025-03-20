import { Link } from 'react-router-dom'
import { Card, EmptyState, PageHeader } from '../components/ui'

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" description="That route does not exist in the dashboard." />
      <Card>
        <EmptyState
          title="Nothing here"
          message="The address you followed does not match any page. Head back to the overview to keep exploring."
          action={
            <Link className="btn btn-primary" to="/">
              Back to the overview
            </Link>
          }
        />
      </Card>
    </>
  )
}
