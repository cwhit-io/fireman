"""
Fiery PPD option definitions for the RoutingPreset form.

Each section is a tuple of (section_title, options_list).
Each option is a tuple of (ppd_key, display_label, choices_list).
Each choice is a tuple of (ppd_value, display_label).

An empty string value "" means "don't send this option" (use printer default).
"""

FIERY_OPTION_SECTIONS = [
    (
        "Media",
        [
            (
                "EFPrintSize",
                "Paper Size",
                [
                    ("", "— printer default —"),
                    ("SameAsPageSize", "Same as Document"),
                    ("Letter", "Letter (8.5×11)"),
                    ("A4", "A4"),
                    ("Tabloid", "Tabloid (11×17)"),
                    ("TabloidExtra", "Tabloid Extra (12×18)"),
                    ("Legal", "Legal (8.5×14)"),
                    ("Statement", "Statement (5.5×8.5)"),
                    ("Executive", "Executive"),
                    ("A3", "A3"),
                    ("A5", "A5"),
                    ("B4", "B4"),
                    ("B5", "B5"),
                    ("SRA3", "SRA3"),
                    ("SRA4", "SRA4"),
                    ("13x19", "13×19"),
                    ("13x19.2R", "13×19.2"),
                    ("12.6x19.2", "12.6×19.2"),
                    ("12.6x18.5", "12.6×18.5"),
                    ("13x18", "13×18"),
                    ("CustomPrintSize", "Custom"),
                ],
            ),
            (
                "EFMediaType",
                "Paper Type",
                [
                    ("", "— printer default —"),
                    ("Plain", "Plain"),
                    ("Recycled", "Recycled"),
                    ("Glossy", "Glossy"),
                    ("CoatedMatteLaser", "Coated Matte"),
                    ("CoatedGlossLaser", "Coated Gloss"),
                    ("Letterhead", "Letterhead"),
                    ("Preprinted", "Preprinted"),
                    ("Prepunched", "Prepunched"),
                    ("Transparency", "Transparency"),
                    ("Tabstock", "Tabstock"),
                    ("Translucent", "Translucent"),
                    ("Labels", "Labels"),
                    ("Envelope", "Envelope"),
                    ("EmbossedPaper", "Embossed"),
                    ("Metallic", "Metallic"),
                    ("Parcel", "Parcel"),
                    ("Synthetic", "Synthetic"),
                    ("NCR", "NCR"),
                ],
            ),
            (
                "EFMediaWeight",
                "Paper Weight (gsm)",
                [
                    ("", "— printer default —"),
                    ("1_300", "All (1–300)"),
                    ("52_65", "52–65"),
                    ("66_80", "66–80"),
                    ("81_100", "81–100"),
                    ("101_127", "101–127"),
                    ("127_150", "127–150"),
                    ("150_216", "150–216"),
                    ("216_256", "216–256"),
                    ("256_300", "256–300"),
                    ("300_360", "300–360"),
                ],
            ),
            (
                "InputSlot",
                "Input Tray",
                [
                    ("", "— printer default —"),
                    ("AutoSelect", "Auto Select"),
                    ("Tray1", "Tray 1"),
                    ("Tray2", "Tray 2"),
                    ("Tray3", "Tray 3"),
                    ("Tray5", "Tray 5"),
                    ("Tray6", "Tray 6"),
                    ("Tray7", "Tray 7"),
                    ("TrayC", "Tray C (Large Capacity)"),
                    ("ManualFeed", "Manual Feed"),
                    ("Interposer", "Interposer"),
                    ("InterposerUpper", "Interposer Upper"),
                    ("InterposerLower", "Interposer Lower"),
                ],
            ),
        ],
    ),
    (
        "Print Queue Action",
        [
            (
                "EFRaster",
                "Queue Action",
                [
                    ("", "— printer default —"),
                    ("False", "Normal (Print)"),
                    ("Hold", "Hold"),
                    ("True", "Process and Hold"),
                    ("RipNHold", "RIP and Hold"),
                    ("PrintNDelete", "Print and Delete"),
                ],
            ),
            (
                "EFDocServer",
                "Document Server",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),
    (
        "Color",
        [
            (
                "EFColorMode",
                "Color Mode",
                [
                    ("", "— printer default —"),
                    ("CMYK", "CMYK (Color)"),
                    ("Grayscale", "Grayscale"),
                ],
            ),
            (
                "EFSimulation",
                "CMYK Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFSimulationDEF", "Fiery Default"),
                    ("SIMNONE", "None"),
                    ("MATCHCOPY", "Match Copy"),
                    ("GRACOL2013", "GRACoL 2013"),
                    ("FOGRA51", "FOGRA51"),
                    ("FOGRA52", "FOGRA52"),
                    ("SWOP2013CRPC5", "SWOP 2013 CRPC5"),
                    ("JAPANCOLOR2011", "Japan Color 2011"),
                    ("DIC", "DIC"),
                    ("TOYOCOATED", "Toyo Coated"),
                ],
            ),
            (
                "EFOutProfile",
                "Output Profile",
                [
                    ("", "— printer default —"),
                    ("EFOutProfileDEF", "Fiery Default"),
                    ("DEFAULT_MEDIA", "Use Media Default"),
                    ("OUT1", "Output 1"),
                    ("OUT2", "Output 2"),
                    ("OUT3", "Output 3"),
                    ("OUT4", "Output 4"),
                    ("OUT5", "Output 5"),
                ],
            ),
            (
                "EFPureBlack",
                "Black Text & Graphics",
                [
                    ("", "— printer default —"),
                    ("EFPureBlackDEF", "Fiery Default"),
                    ("BLACKPUREON", "Pure Black On"),
                    ("BLACKRICHON", "Rich Black On"),
                    ("BLACKNORMAL", "Normal"),
                ],
            ),
            (
                "EFBlkOvpCtrl",
                "Black Overprint",
                [
                    ("", "— printer default —"),
                    ("EFBlkOvpCtrlDEF", "Fiery Default"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTONLY", "Text Only"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFSpotColors",
                "Spot Color Matching",
                [
                    ("", "— printer default —"),
                    ("EFSpotColorsDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFTrapping",
                "Auto Trapping",
                [
                    ("", "— printer default —"),
                    ("EFTrappingDEF", "Fiery Default"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFCompOverprint",
                "Composite Overprint",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFHPBlack",
                "Black Detection",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFSubstColors",
                "Substitute Colors",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFMltClrPrntMap",
                "2-Color Print Mapping",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),
    (
        "Layout",
        [
            (
                "EFDuplex",
                "Duplex",
                [
                    ("", "— printer default —"),
                    ("False", "Simplex (1-sided)"),
                    ("TopTop", "Duplex Long-Edge"),
                    ("TopBottom", "Duplex Short-Edge"),
                ],
            ),
            (
                "EFDrvOrientation",
                "Orientation",
                [
                    ("", "— printer default —"),
                    ("Portrait", "Portrait"),
                    ("Landscape", "Landscape"),
                ],
            ),
            (
                "EFScaleToFit",
                "Scale to Fit",
                [
                    ("", "— printer default —"),
                    ("OFF", "Off"),
                    ("ScaleToPaperSize", "Scale to Paper Size"),
                    ("ScaleToImageableArea", "Scale to Imageable Area"),
                ],
            ),
            (
                "EFMarginZero",
                "Full Bleed Printing",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFBorderlessPrint",
                "Print to Max Printable Area",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFEngRotate180",
                "Rotate 180°",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                    ("LargePaperOnly", "Large Paper Only"),
                    ("SmallPaperOnly", "Small Paper Only"),
                ],
            ),
            (
                "EFDrvMirror",
                "Mirror Print",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFNUpOption",
                "N-Up Layout",
                [
                    ("", "— printer default —"),
                    ("1UP", "1-Up (Normal)"),
                    ("2ULH", "2-Up Landscape (H)"),
                    ("2URV", "2-Up Portrait (V)"),
                    ("4ULH", "4-Up Landscape (H)"),
                    ("4ULV", "4-Up Portrait (V)"),
                    ("4URH", "4-Up Rotated (H)"),
                    ("4URV", "4-Up Rotated (V)"),
                ],
            ),
            (
                "EFNUpBoundingBox",
                "N-Up Border",
                [
                    ("", "— printer default —"),
                    ("False", "No Border"),
                    ("True", "With Border"),
                ],
            ),
            (
                "EFImageFlag",
                "Image Shift",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageAlign",
                "Align Front & Back Images",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageUnit",
                "Image Shift Units",
                [
                    ("", "— printer default —"),
                    ("Inches", "Inches"),
                    ("MM", "Millimeters"),
                    ("Points", "Points"),
                ],
            ),
        ],
    ),
    (
        "Output & Delivery",
        [
            (
                "EFOutputBin",
                "Output Tray",
                [
                    ("", "— printer default —"),
                    ("AutoSelect", "Auto Select"),
                    ("Upper", "Upper Tray"),
                    ("Lower", "Lower Tray"),
                    ("Folder", "Folder"),
                    ("Booklet", "Booklet Tray"),
                    ("UpperShift", "Upper Shift"),
                    ("LowerShift", "Lower Shift"),
                    ("TopTrayAuto", "Top Tray Auto"),
                    ("Stacker", "Stacker"),
                    ("Stacker2_2", "Stacker 2"),
                    ("ExternalFinisher", "External Finisher"),
                ],
            ),
            (
                "EFSort",
                "Collate",
                [
                    ("", "— printer default —"),
                    ("Sort", "Sort (Collated)"),
                    ("False", "Uncollated"),
                ],
            ),
            (
                "EFPageDelivery",
                "Page Delivery Order",
                [
                    ("", "— printer default —"),
                    ("SameOrderFaceDown", "Same Order Face Down"),
                    ("SameOrderFaceUp", "Same Order Face Up"),
                    ("ReverseOrderFaceDown", "Reverse Order Face Down"),
                    ("ReverseOrderFaceUp", "Reverse Order Face Up"),
                ],
            ),
            (
                "EFOffsetJobs",
                "Job Offset / Shift",
                [
                    ("", "— printer default —"),
                    ("EngineDefault", "Engine Default"),
                    ("False", "Off"),
                    ("Sets", "Between Sets"),
                    ("Jobs", "Between Jobs"),
                ],
            ),
            (
                "EFLimitlessOutputOpt",
                "Limitless Finisher Tray",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
        ],
    ),
    (
        "Finishing",
        [
            (
                "EFStapler",
                "Staple",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("1LeftA", "1 Staple — Top Left"),
                    ("1RightA", "1 Staple — Top Right"),
                    ("1UpLeftH", "1 Staple — Left Horizontal"),
                    ("1UpLeftS", "1 Staple — Left Skewed"),
                    ("1UpLeftV", "1 Staple — Left Vertical"),
                    ("1UpRightH", "1 Staple — Right Horizontal"),
                    ("1UpRightS", "1 Staple — Right Skewed"),
                    ("1UpRightV", "1 Staple — Right Vertical"),
                    ("2Left", "2 Staples — Left Edge"),
                    ("2Right", "2 Staples — Right Edge"),
                    ("2Up", "2 Staples — Top Edge"),
                    ("Center", "Center"),
                ],
            ),
            (
                "StapleLocation",
                "Core Stapler",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("SinglePortrait", "Single Portrait"),
                ],
            ),
            (
                "EFPunchEdge",
                "Punch Edge",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Left", "Left"),
                    ("Right", "Right"),
                    ("Top", "Top"),
                ],
            ),
            (
                "EFPunchHoleType",
                "Punch Holes",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("2Even", "2 Holes"),
                    ("3Even", "3 Holes"),
                    ("4Even", "4 Holes"),
                    ("MultiPunch", "Multi-Punch"),
                    ("DoubleMultiPunch", "Double Multi-Punch"),
                ],
            ),
            (
                "EFFold",
                "Fold Style",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("HalfFold", "Half Fold"),
                    ("HalfZFold", "Half Z-Fold"),
                    ("HalfZFoldLargeMedia", "Half Z-Fold (Large Media)"),
                    ("TriFold", "Tri-Fold"),
                    ("Zfold", "Z-Fold"),
                    ("DoubleHalfFold", "Double Half Fold"),
                    ("GateFold", "Gate Fold"),
                    ("CollateHalfFold", "Collate Half Fold"),
                    ("CollateZfold", "Collate Z-Fold"),
                    ("CollateTriFold", "Collate Tri-Fold"),
                ],
            ),
            (
                "EFFoldOrder",
                "Fold Order",
                [
                    ("", "— printer default —"),
                    ("In", "In"),
                    ("Out", "Out"),
                ],
            ),
            (
                "EFTrimmer",
                "Trim",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFSquareFold",
                "Book Fold (Square Spine)",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFWireBind",
                "Twin Loop Bind",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
        ],
    ),
    (
        "Booklet",
        [
            (
                "EFRIPBooklet",
                "Booklet Type",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("TwoUp", "2-Up Saddle"),
                    ("TwoUpRight", "2-Up Saddle (Right Binding)"),
                    ("Perfect", "Perfect Binding"),
                    ("PerfectRight", "Perfect Binding (Right)"),
                    ("NestSaddleL", "Nested Saddle Left"),
                    ("NestSaddleR", "Nested Saddle Right"),
                    ("Speed", "Speed"),
                    ("Double", "Double"),
                    ("NestSaddleT", "Nested Saddle Top"),
                    ("PerfectTop", "Perfect Top"),
                    ("TwoUpTop", "2-Up Top"),
                ],
            ),
            (
                "EFBookCoverEnabled",
                "Cover Enabled",
                [
                    ("", "— printer default —"),
                    ("False", "No"),
                    ("True", "Yes"),
                ],
            ),
            (
                "EFBookFrCover",
                "Front Cover",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Side1", "Side 1"),
                    ("Side2", "Side 2"),
                    ("Both", "Both Sides"),
                    ("Blank", "Blank"),
                ],
            ),
            (
                "EFBookBkCover",
                "Back Cover",
                [
                    ("", "— printer default —"),
                    ("None", "None"),
                    ("Side1", "Side 1"),
                    ("Side2", "Side 2"),
                    ("Both", "Both Sides"),
                    ("Blank", "Blank"),
                ],
            ),
            (
                "EFBookletCreep",
                "Creep Adjustment",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("Plain", "Plain"),
                    ("Thick", "Thick"),
                ],
            ),
            (
                "EFBookletReduce",
                "Shrink to Fit",
                [
                    ("", "— printer default —"),
                    ("True", "Yes"),
                    ("False", "No"),
                    ("UseImageable", "Use Imageable Area"),
                ],
            ),
            (
                "EFBookNumSheetPerSubset",
                "Sheets per Subset (Saddle)",
                [
                    ("", "— printer default —"),
                ]
                + [(str(n), str(n)) for n in range(2, 21)],
            ),
            (
                "EFBookCentering",
                "Centering Adjustment",
                [
                    ("", "— printer default —"),
                    ("Bottom", "Bottom"),
                    ("Middle", "Middle"),
                ],
            ),
        ],
    ),
    (
        "Print Quality",
        [
            (
                "EFCopierMode",
                "Halftone Mode",
                [
                    ("", "— printer default —"),
                    ("Pattern1", "Pattern 1"),
                    ("Pattern2", "Pattern 2"),
                    ("Pattern3", "Pattern 3 (Default)"),
                    ("Pattern4", "Pattern 4"),
                    ("Pattern5", "Pattern 5"),
                    ("Pattern6", "Pattern 6"),
                    ("Pattern7", "Pattern 7"),
                    ("VeryFine", "Very Fine"),
                ],
            ),
            (
                "EFHTScreen",
                "Halftone Simulation",
                [
                    ("", "— printer default —"),
                    ("Contone", "Contone"),
                    ("AppDef", "Application Defined"),
                    ("Newsprint", "Newsprint"),
                    ("Screen1", "Screen 1"),
                    ("Screen2", "Screen 2"),
                    ("Screen3", "Screen 3"),
                ],
            ),
            (
                "EFCompression",
                "Image Quality",
                [
                    ("", "— printer default —"),
                    ("BestQuality", "Best"),
                    ("NormalQuality", "Normal"),
                ],
            ),
            (
                "EFTextGfxQual",
                "Text / Graphics Quality",
                [
                    ("", "— printer default —"),
                    ("Normal", "Normal"),
                    ("Best", "Best"),
                ],
            ),
            (
                "EFTonerReduce",
                "Toner Reduction",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFMaxPrintDensity",
                "Max Print Density",
                [
                    ("", "— printer default —"),
                    ("False", "Normal"),
                    ("True", "Maximum"),
                ],
            ),
            (
                "EFBrightness",
                "Brightness",
                [
                    ("", "— printer default —"),
                    ("0.24", "+24% (Lightest)"),
                    ("0.16", "+16% (Lighter)"),
                    ("0.08", "+8% (Light)"),
                    ("00.00", "0% (Normal)"),
                    ("-0.08", "-8% (Dark)"),
                    ("-0.16", "-16% (Darker)"),
                    ("-0.24", "-24% (Darkest)"),
                ],
            ),
            (
                "EFGlossAdjustment",
                "Gloss Adjustment",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageSmooth",
                "Image Smoothing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFResolution",
                "Resolution",
                [
                    ("", "— printer default —"),
                    ("1200x1200dpi", "1200×1200 dpi"),
                ],
            ),
        ],
    ),
    (
        "Slip Sheet",
        [
            (
                "EFSlipsheet",
                "Slip Sheet",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFSlipSheetBoundary",
                "Insert Between",
                [
                    ("", "— printer default —"),
                    ("Sheets", "Sheets"),
                    ("Copies", "Copies"),
                    ("Sets", "Sets"),
                    ("BeforeJob", "Before Job"),
                    ("AfterJob", "After Job"),
                    ("BeforeAndAfter", "Before and After"),
                ],
            ),
            (
                "EFInterlvMedia",
                "Slip Sheet Paper Type",
                [
                    ("", "— printer default —"),
                    ("Plain", "Plain"),
                    ("Glossy", "Glossy"),
                    ("CoatedGlossLaser", "Coated Gloss"),
                    ("CoatedMatteLaser", "Coated Matte"),
                    ("Tabstock", "Tabstock"),
                ],
            ),
            (
                "EFInterlvTray",
                "Slip Sheet Paper Source",
                [
                    ("", "— printer default —"),
                    ("AutoSelect", "Auto Select"),
                    ("Tray1", "Tray 1"),
                    ("Tray2", "Tray 2"),
                    ("Tray3", "Tray 3"),
                    ("ManualFeed", "Manual Feed"),
                ],
            ),
        ],
    ),
    (
        "Cover Page",
        [
            (
                "EFPrintCover",
                "Separator / Cover Page",
                [
                    ("", "— printer default —"),
                    ("False", "None"),
                    ("BeforeJob", "Before Job"),
                    ("AfterJob", "After Job"),
                    ("BeforeAndAfter", "Before and After"),
                ],
            ),
        ],
    ),
    (
        "Color — Profiles & Rendering",
        [
            (
                "EFRGBOverride",
                "RGB Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFRGBOverrideDEF", "Fiery Default"),
                    ("SRGB", "sRGB"),
                    ("ADOBERGB", "Adobe RGB"),
                    ("ECIRGB", "ECI RGB"),
                    ("APPLE13", "Apple RGB"),
                    ("FIERYRGB", "Fiery RGB"),
                    ("EFIRGB", "EFI RGB"),
                ],
            ),
            (
                "EFEmbeddedRGB",
                "Use RGB Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("EFEmbeddedRGBDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFColorRendDict",
                "RGB Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("EFColorRendDictDEF", "Fiery Default"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                ],
            ),
            (
                "EFRGBSep",
                "Separate RGB/Lab to CMYK",
                [
                    ("", "— printer default —"),
                    ("EFRGBSepDEF", "Fiery Default"),
                    ("SEPSIM", "Simulation"),
                    ("SEPOUT", "Output Profile"),
                ],
            ),
            (
                "EFKOnlyGrayRGB",
                "Print RGB Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayRGBDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
            (
                "EFEmbeddedCMYK",
                "Use CMYK Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("EFEmbeddedCMYKDEF", "Fiery Default"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFCMYKColorRendDict",
                "CMYK Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                    ("XGAM", "Pure Gamut"),
                ],
            ),
            (
                "EFBlackPointCompCMYK",
                "Black Point Compensation",
                [
                    ("", "— printer default —"),
                    ("EFBlackPointCompCMYKDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("ON", "On"),
                ],
            ),
            (
                "EFKOnlyGrayCMYK",
                "Print CMYK Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayCMYKDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
            (
                "EFGrayOverride",
                "Grayscale Source Profile",
                [
                    ("", "— printer default —"),
                    ("EFGrayOverrideDEF", "Fiery Default"),
                    ("dotgain10", "Dot Gain 10%"),
                    ("dotgain15", "Dot Gain 15%"),
                    ("dotgain20", "Dot Gain 20%"),
                    ("dotgain25", "Dot Gain 25%"),
                    ("dotgain30", "Dot Gain 30%"),
                    ("graygamma18", "Gray Gamma 1.8"),
                    ("graygamma22", "Gray Gamma 2.2"),
                ],
            ),
            (
                "EFEmbeddedGray",
                "Use Gray Embedded Profiles",
                [
                    ("", "— printer default —"),
                    ("ON", "On"),
                    ("OFF", "Off"),
                ],
            ),
            (
                "EFGrayColorRendDict",
                "Grayscale Rendering Intent",
                [
                    ("", "— printer default —"),
                    ("PHOTOGRAPHIC", "Photographic"),
                    ("PRESENTATION", "Presentation"),
                    ("RELATIVE", "Relative Colorimetric"),
                    ("ABSOLUTE", "Absolute Colorimetric"),
                ],
            ),
            (
                "EFKOnlyGray",
                "Print Gray Using Black Only",
                [
                    ("", "— printer default —"),
                    ("EFKOnlyGrayDEF", "Fiery Default"),
                    ("OFF", "Off"),
                    ("TEXTGRAPHICS", "Text & Graphics"),
                    ("TEXTGRAPHICSIMAG", "Text, Graphics & Images"),
                ],
            ),
        ],
    ),
    (
        "Color — Separations",
        [
            (
                "EFSeparations",
                "Combine Separations",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFColorSelectC",
                "Cyan (C)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectM",
                "Magenta (M)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectY",
                "Yellow (Y)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFColorSelectK",
                "Black (K)",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
        ],
    ),
    (
        "Image Enhancement",
        [
            (
                "EFImageWiseRange",
                "Apply Image Enhancement",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFImageWise_RangeType",
                "Image Enhance Range",
                [
                    ("", "— printer default —"),
                    ("AllPages", "All Pages"),
                    ("Pages", "Selected Pages"),
                    ("Sheets", "Selected Sheets"),
                ],
            ),
        ],
    ),
    (
        "Control & Diagnostics",
        [
            (
                "EFPostFlight",
                "Postflight",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("ReportConcise", "Report (Concise)"),
                    ("TestPage", "Test Page"),
                    ("ColorCodedJob", "Color Coded Job"),
                    ("All", "All"),
                ],
            ),
            (
                "EFControlBar",
                "Control Bar",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("Default", "Default"),
                ],
            ),
            (
                "EFEngTabShift",
                "Tab Shift",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
            (
                "EFTrayAlignment",
                "Tray Alignment",
                [
                    ("", "— printer default —"),
                    ("True", "On"),
                    ("False", "Off"),
                ],
            ),
            (
                "EFSubsetFinishingInUse",
                "Subset Finishing",
                [
                    ("", "— printer default —"),
                    ("False", "Off"),
                    ("True", "On"),
                ],
            ),
        ],
    ),
]


def build_fiery_sections(fiery_options: dict) -> list:
    """
    Return a list of section dicts with pre-computed selection state,
    ready to iterate in the template.

    Each section: {"title": str, "options": [{"key", "label", "choices": [(val, label, is_selected)]}]}
    """
    result = []
    for section_title, options in FIERY_OPTION_SECTIONS:
        built_opts = []
        for key, label, choices in options:
            current = fiery_options.get(key, "")
            built_choices = [(v, lbl, v == current) for v, lbl in choices]
            built_opts.append({"key": key, "label": label, "choices": built_choices})
        result.append({"title": section_title, "options": built_opts})
    return result
