#import "@preview/tiaoma:0.2.0"

#let csv_file = "scripts/open-dancing-playlist.csv" // Update if necessary
#let playlist_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" // Replace with link to actual playlist
#let feedback_url = "https://example.com"

#let default_left_margin = 71pt // Left margin size in pt for A4
#let left_margin_change = 36pt // Width of first column

#set page(
  margin: (left: default_left_margin - left_margin_change),
  footer: context [
    #set align(center)
    #counter(page).display(
      "1 of 1",
      both: true,
    )
  ],
)

#set page(margin: (
  top: 160pt
))


#set page(header: context {
  if here().page() <= 1 [
    #set align(right)
    #stack(
        dir: ltr,
        spacing: 8pt,
        text(
          [
            Tanzquotient Zürich (TQ)\
            VSETH Commission\
            Universitätstrasse 6\
            8092 Zürich\
            kontakt\@tanzquotient.org\
            www.tanzquotient.org
          ]
        ),
        image(
          "assets/tanzquotient_logo.png",
          height: 90pt
        )
    )
  ] else [
    #block(
      inset: (top: -30pt, left: left_margin_change),
      grid(
        columns: (0.9fr, auto),
        align: (left + horizon, right + horizon),
        stack(
          dir: ttb,
          image(
            "assets/vseth_logo_bunt.svg",
            height: 40pt
          ),
        ),
        stack(
          dir: ltr,
          spacing: 8pt,
          text(
            [
              *Tanzquotient Zürich (TQ)*\
              VSETH Commission
            ]
          ),
          image(
            "assets/tanzquotient_logo.png",
            height: 30pt
          ),
        ),
      )
    )
  ]
})

// Colour links
#show link: this => {
  let label-color = green
  let default-color = rgb("#ff66ff")

  underline(text(blue)[#this])
}

#pad(
  x: left_margin_change,
  [
    = Open Dancing DATE-HERE
    == Playlist by AUTHOR-HERE
  ],
)

// Set text size a bit smaller to fit everything
#set text(
  size: 9pt,
)

#let mycounter = counter("mycounter")
#let results = csv(
  row-type: dictionary,
  csv_file
)
#show table.cell.where(y: 0): strong
#table(
  fill: (x, y) =>
    if x != 0 {
      if y == 0 { rgb("d9d9d9") }
      else if calc.even(y) { rgb("f3f3f3") }
    },
  inset: 7pt,
  stroke: (x, y) =>
    if x == 0 { none }
    else { 1pt },
  columns:
    (
      auto,
      // auto, // Comment in for Playlist index
      auto,
      auto,
      auto,
      auto,
    ),
    [Time],
    // [Nr.], // Comment in for Playlist index
    [Duration],
    [Title],
    [Artist],
    [Dance#footnote[The dances mentioned here are just a suggestion. Feel free to add your own style!]],
  ..results.map(
      v => (
        [#v.at("Start Time")],
        // [#v.at("index")], // Comment in for Playlist index
        [#v.at("Duration (min:sec)")],
        [#v.at("Track Name")],
        [#v.at("Artists")],
        [#v.at("Suggested Dance")],
      )
    ).flatten(),
)

#pad(
  x: left_margin_change,
  grid(
    columns: (auto, auto, auto, auto),
    rows: (auto, auto, auto),
    gutter: 15pt,

    grid.cell(
      rowspan: 2,
      tiaoma.barcode(
        playlist_url,
        "QRCode",
        options: (
          scale: 1.5,
        ),
      ),
    ),
    text(size: 20pt, [*Playlist*]),
    text(size: 20pt, [*Feedback & Song requests*]),
    grid.cell(
      rowspan: 2,
      tiaoma.barcode(feedback_url,"QRCode",options: (scale: 1.5,),),
    ),
    link(playlist_url),
    link(feedback_url),
  )
)
