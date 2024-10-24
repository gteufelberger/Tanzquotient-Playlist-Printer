#import "@preview/tablex:0.0.8": tablex, hlinex, vlinex
#import "@preview/tiaoma:0.2.0"

#let csv_file = "scripts/open-dancing-playlist.csv" // Update if necessary
#let playlist_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" // Replace with link to actual playlist


#set page(
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


#set page(header: locate(loc => {
  if counter(page).at(loc).first() <= 1 [
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
      inset: (top: -30pt),
      tablex(
        columns: (1fr, 1fr),
        align: (left + horizon, right + horizon),
        auto-lines: false,
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
}))

= Open Dancing DATE-HERE
== Playlist by AUTHOR-HERE

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
  fill: (_, y) =>
    if y == 0 { rgb("d9d9d9") }
    else if calc.even(y) { rgb("f3f3f3") },
  inset: 7pt,
  columns:
    (
      auto,
      // auto, // Comment in for Playlist index
      auto,
      auto,
      auto,
    ),
    [Time],
    // [Nr.], // Comment in for Playlist index
    [Title],
    [Artist],
    [Dance#footnote[The dances mentioned here are just a suggestion. Feel free to add your own style!]],
  ..results.map(
      v => (
        [#v.at("Start Time")],
        // [#v.at("index")], // Comment in for Playlist index
        [#v.at("Track Name")],
        [#v.at("Artists")],
        [#v.at("Suggested Dance")],
      )
    ).flatten(),
)

// QR Code
#stack(
  dir: ltr,
  spacing: 8pt,
  tiaoma.barcode(
    playlist_url,
    "QRCode",
    options: (
      scale: 1.5,
    ),
  ),
  text(
    [
      #text(
        size: 20pt,
        [*Playlist*]
      )
      \
      \
      #text(
        size: 13pt, // Slightly larger link text
        fill: blue,
        [
          #underline[
            #link(playlist_url)
          ]
        ]
      )
    ]
  ),
)
