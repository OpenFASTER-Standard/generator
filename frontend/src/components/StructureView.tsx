import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { ComplexType, DeclarationsResponse, SimpleType, StructureResponse } from "@/lib/api"

interface StructureViewProps {
  structure: StructureResponse
  declarations: DeclarationsResponse
  search: string
}

function matchesSearch(name: string | null, search: string): boolean {
  if (!search) return true
  return (name ?? "").toLowerCase().includes(search.toLowerCase())
}

function ComplexTypeCard({ type }: { type: ComplexType }) {
  return (
    <Card id={type.uri} className="mb-3">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {type.name ?? "(anonymous)"}
          {type.abstract && <Badge variant="outline">abstract</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        {type.extends && <div>extends {type.extends}</div>}
        <div>{type.contentModel.kind} ({type.contentModel.particles.length} particle(s))</div>
        {type.attributeUses.length > 0 && (
          <div>{type.attributeUses.length} attribute use(s)</div>
        )}
        {type.identityConstraints.length > 0 && (
          <div>{type.identityConstraints.length} identity constraint(s)</div>
        )}
      </CardContent>
    </Card>
  )
}

function SimpleTypeCard({ type }: { type: SimpleType }) {
  const facetsText = Object.entries(type.facets)
    .map(([key, value]) => `${key}=${value}`)
    .join(", ")
  return (
    <Card id={type.uri} className="mb-3">
      <CardHeader>
        <CardTitle className="text-base">{type.name ?? "(anonymous)"}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        {facetsText && <div>facets: {facetsText}</div>}
        {type.patterns.map((pattern, index) => (
          <code key={index} className="block break-all rounded bg-muted p-2 font-mono text-xs">
            {pattern}
          </code>
        ))}
        {type.enumeration.length > 0 && <div>enumeration: {type.enumeration.join(", ")}</div>}
      </CardContent>
    </Card>
  )
}

export function StructureView({ structure, search }: StructureViewProps) {
  return (
    <div>
      {Object.entries(structure).map(([namespace, block]) => {
        const complexTypes = block.complexTypes.filter((t) => matchesSearch(t.name, search))
        const simpleTypes = block.simpleTypes.filter((t) => matchesSearch(t.name, search))
        if (complexTypes.length === 0 && simpleTypes.length === 0) return null
        return (
          <section key={namespace} className="mb-8">
            <h3 className="mb-2 border-b pb-1 text-lg font-semibold">{namespace}</h3>
            {complexTypes.map((type) => (
              <ComplexTypeCard key={type.uri} type={type} />
            ))}
            {simpleTypes.map((type) => (
              <SimpleTypeCard key={type.uri} type={type} />
            ))}
          </section>
        )
      })}
    </div>
  )
}
