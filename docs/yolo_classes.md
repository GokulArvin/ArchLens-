# YOLOv8n (COCO-pretrained) Class Inventory (Sprint 3 / D11)

Model: `yolov8n.pt` (ultralytics, COCO-pretrained, 80 classes).

## Full class list

| id | class |
|---|---|
| 0 | person |
| 1 | bicycle |
| 2 | car |
| 3 | motorcycle |
| 4 | airplane |
| 5 | bus |
| 6 | train |
| 7 | truck |
| 8 | boat |
| 9 | traffic light |
| 10 | fire hydrant |
| 11 | stop sign |
| 12 | parking meter |
| 13 | bench |
| 14 | bird |
| 15 | cat |
| 16 | dog |
| 17 | horse |
| 18 | sheep |
| 19 | cow |
| 20 | elephant |
| 21 | bear |
| 22 | zebra |
| 23 | giraffe |
| 24 | backpack |
| 25 | umbrella |
| 26 | handbag |
| 27 | tie |
| 28 | suitcase |
| 29 | frisbee |
| 30 | skis |
| 31 | snowboard |
| 32 | sports ball |
| 33 | kite |
| 34 | baseball bat |
| 35 | baseball glove |
| 36 | skateboard |
| 37 | surfboard |
| 38 | tennis racket |
| 39 | bottle |
| 40 | wine glass |
| 41 | cup |
| 42 | fork |
| 43 | knife |
| 44 | spoon |
| 45 | bowl |
| 46 | banana |
| 47 | apple |
| 48 | sandwich |
| 49 | orange |
| 50 | broccoli |
| 51 | carrot |
| 52 | hot dog |
| 53 | pizza |
| 54 | donut |
| 55 | cake |
| 56 | chair |
| 57 | couch |
| 58 | potted plant |
| 59 | bed |
| 60 | dining table |
| 61 | toilet |
| 62 | tv |
| 63 | laptop |
| 64 | mouse |
| 65 | remote |
| 66 | keyboard |
| 67 | cell phone |
| 68 | microwave |
| 69 | oven |
| 70 | toaster |
| 71 | sink |
| 72 | refrigerator |
| 73 | book |
| 74 | clock |
| 75 | vase |
| 76 | scissors |
| 77 | teddy bear |
| 78 | hair drier |
| 79 | toothbrush |

## Assessment (feeds D12)

None of these 80 COCO classes describe architecture-diagram components
(services, databases, queues, gateways, etc.) - COCO is a photograph
object-detection dataset (people, vehicles, animals, furniture,
household items). A diagram box labeled "Database" will not match any
COCO class by label; the detector may still fire on diagram content
that incidentally resembles a COCO object (e.g. a person icon), but
that's coincidental, not semantically meaningful for our task.

Per the plan's non-negotiable rule ("start with pretrained models...
do not spend the 50 days training a large detector from scratch"),
Sprint 3's approach is therefore: run the pretrained detector as-is,
and - per D12 - treat *any* detection above the confidence threshold
as a generic `architecture_component` candidate, ignoring its COCO
label entirely rather than trying to map COCO semantics onto diagram
semantics. The real precision/recall this yields against our hand-
annotated ground truth is measured honestly in D13-D15, not assumed.